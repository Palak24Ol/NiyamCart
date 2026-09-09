"""Durable database-backed worker. Run with --once for operations/rehearsal."""

import argparse
import asyncio
import logging
import os

from .journey_tasks import run_due_tasks

logger = logging.getLogger(__name__)


async def worker_loop(database):
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(run_due_tasks, database)
            await asyncio.to_thread(observe_orders, database)
        except Exception as error:
            logger.warning("Journey worker cycle failed: %s", type(error).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    from .main import create_app

    app = create_app(os.getenv("DATABASE_URL", "sqlite:///./niyamcart.db"))
    app.state.db.create_schema()
    print(f"Processed {run_due_tasks(app.state.db)} due journey tasks")
    observe_orders(app.state.db)
    app.state.db.close()


def observe_orders(database):
    """Follow verified orders without coupling notification failures to payment finalisation."""
    from sqlalchemy import select, update

    from .audit import append_audit
    from .commerce import load_cart
    from .commerce_models import Order
    from .journey_aftercare import order_data
    from .journey_models import JourneyCart, ShoppingMission
    from .journey_tasks import notify

    with database.session_factory() as db:
        identities = list(db.scalars(select(Order.id).where(Order.status == "paid")))
    for identity in identities:
        with database.session_factory() as db:
            db.execute(update(Order).where(Order.id == identity).values(status=Order.status))
            order = db.get(Order, identity)
            cart = load_cart(db, order.cart_id)
            link = db.get(JourneyCart, cart.id)
            customer_id = (
                link.customer_id
                if link
                else (cart.fulfillment.customer_id if cart.fulfillment else None)
            )
            if customer_id is None:
                continue
            notify(
                db,
                customer_id,
                "paid:" + identity,
                "Your order is confirmed",
                "Payment independently verified. Carrier updates will appear when received.",
                "/orders?order=" + identity,
            )
            if link and link.mission_id:
                mission = db.get(ShoppingMission, link.mission_id)
                if (
                    mission
                    and mission.status == "checkout"
                    and mission.plan.get("cart_id") == cart.id
                ):
                    mission.status = "purchased"
                    append_audit(
                        db, "mission", mission.id, "mission_purchased", {"order_id": identity}
                    )
            summary = order_data(db, order)
            if summary["is_late"]:
                notify(
                    db,
                    customer_id,
                    "late:" + identity,
                    "Your delivery estimate has passed",
                    "The catalogue estimate has passed without a delivered event. "
                    "Ask the merchant for an update from your order page.",
                    "/orders?order=" + identity,
                )
            db.commit()


if __name__ == "__main__":
    main()
