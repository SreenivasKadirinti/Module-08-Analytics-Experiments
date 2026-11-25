import random
import sys

from datetime import timedelta

import pandas as pd

from app.database.connection import SessionLocal
from app.models.tables import DimProduct, StagingEvent
from app.services.aggregation_service import aggregate_daily_metrics

PATH = sys.argv[1] if len(sys.argv) > 1 else r"D:\2019-Oct.csv"
CUTOFF = pd.Timestamp("2019-10-04", tz="UTC")   # loads 1 to 3 October 2019
USER_SHARE = 50                                  # keep 1 in 50 users (whole users, so journeys stay together)
EXTRA_IMPRESSIONS_PER_VIEW = 4                   # makes CTR realistic
PLACEMENTS = ["home_carousel", "pdp_similar", "cart_recommend", "search_sponsored"]
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 7   # how many days to spread the data over


def load_rows() -> pd.DataFrame:
    parts = []
    for chunk in pd.read_csv(PATH, chunksize=500_000):
        t = pd.to_datetime(chunk["event_time"], utc=True)
        chunk["event_time"] = t
        parts.append(chunk[(chunk["user_id"] % USER_SHARE == 0) & (t < CUTOFF)])
        if t.max() >= CUTOFF:      # file is time-ordered, so we can stop early
            break
    df = pd.concat(parts)
    df = df[df["event_type"].isin(["view", "cart", "purchase"])]
    return df.sort_values("event_time")


def main():
    rng = random.Random(1)
    print(f"Reading {PATH} ...")
    df = load_rows()
    print(f"Kept {len(df)} source rows")

    db = SessionLocal()
    try:
        db.query(StagingEvent).filter(StagingEvent.event_id.like("kg-%")).delete(synchronize_session=False)
        db.commit()

        # Products (category comes from the first part of category_code)
        known = {r[0] for r in db.query(DimProduct.product_id).all()}
        for _, r in df.drop_duplicates("product_id").iterrows():
            pid = f"kg-{r['product_id']}"
            if pid not in known:
                cat = r.get("category_code")
                db.add(DimProduct(
                    product_id=pid,
                    brand_id=str(r.get("brand")),
                    category_id=str(cat).split(".")[0] if pd.notna(cat) else "unknown",
                    product_name=str(r["product_id"]),
                ))
        db.commit()

        # Events
        last_imp, events, days = {}, [], set()
        for i, r in enumerate(df.itertuples(index=False)):
            ts = r.event_time.to_pydatetime() + timedelta(days=int(r.user_id) % DAYS)
            days.add(ts.date())
            user, pid = f"kg-{r.user_id}", f"kg-{r.product_id}"
            model = "v2.1.0" if r.user_id % 2 == 0 else "v2.2.0"
            common = dict(product_id=pid, user_ref=user, session_id=str(r.user_session), model_version=model)
            place = rng.choice(PLACEMENTS)

            if r.event_type == "view":
                imp = f"kg-imp-{i}"
                last_imp[(user, pid)] = imp
                events.append(StagingEvent(event_id=f"kg-{i}-i", event_type="impression",
                                           impression_id=imp, placement_id=place, occurred_at=ts, **common))
                events.append(StagingEvent(event_id=f"kg-{i}-c", event_type="click",
                                           impression_id=imp, placement_id=place, occurred_at=ts, **common))
                for j in range(EXTRA_IMPRESSIONS_PER_VIEW):
                    events.append(StagingEvent(event_id=f"kg-{i}-x{j}", event_type="impression",
                                               impression_id=f"kg-imp-{i}-x{j}", placement_id=place,
                                               occurred_at=ts, **common))
            else:
                etype = "add_to_cart" if r.event_type == "cart" else "purchase"
                payload = {"amount": float(r.price)} if etype == "purchase" else None
                events.append(StagingEvent(event_id=f"kg-{i}-e", event_type=etype,
                                           impression_id=last_imp.get((user, pid)), placement_id=place,
                                           occurred_at=ts, raw_payload=payload, **common))

        db.bulk_save_objects(events)
        db.commit()
        print(f"Inserted {len(events)} events across {len(days)} day(s)")

        for d in sorted(days):
            print(aggregate_daily_metrics(db, d))
    finally:
        db.close()


if __name__ == "__main__":
    main()