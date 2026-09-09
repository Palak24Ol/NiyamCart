"""Independent HTTP buyer client: discover -> select -> quote -> human review.

Set NIYAMCART_BUYER_KEY to a short-lived quote-only key created in My journey.
This reference client uses deterministic selection, not a hidden LLM or autonomous payment.
"""

import argparse
import json
import os
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(
            "Redirects are disabled so buyer credentials stay with the chosen merchant"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--storefront", default="http://localhost:3000")
    parser.add_argument("--query", default="shirt")
    parser.add_argument("--budget-paise", type=int, default=200_000)
    args = parser.parse_args()
    key = os.getenv("NIYAMCART_BUYER_KEY", "")
    if not key:
        parser.error("Set NIYAMCART_BUYER_KEY using a temporary key from My journey")
    origin = urlparse(args.base)
    if origin.scheme != "https" and origin.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Use HTTPS for a remote merchant")
    opener = build_opener(NoRedirect())

    def call(path, payload=None):
        url = urljoin(args.base, path)
        parsed = urlparse(url)
        if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
            raise ValueError("Merchant contract referred to a different origin")
        headers = {"content-type": "application/json"}
        if payload is not None:
            headers["authorization"] = "Bearer " + key
        request = Request(
            url, data=json.dumps(payload).encode() if payload else None, headers=headers
        )
        with opener.open(request, timeout=20) as response:
            return json.load(response)

    try:
        contract = call("/.well-known/buyer-commerce.json")
        catalog = call(contract["catalog"])
        policy = call(contract["policy"])
        print(
            f"Discovered {len(catalog['products'])} products "
            f"and {len(policy['rules'])} policy rules"
        )
        candidates = [
            p
            for p in catalog["products"]
            if p["availability"]["in_stock"]
            and all(word.casefold() in p["name"].casefold() for word in args.query.split())
        ]
        candidates.sort(
            key=lambda p: (
                p["price"]["amount_paise"] + (0 if p["attributes"]["free_delivery"] else 4900)
            )
        )
        if not candidates:
            raise ValueError("No matching in-stock product; refine --query")
        product = candidates[0]
        quote = call(
            contract["quote"],
            {
                "product_ids": [product["product_id"]],
                "budget_paise": args.budget_paise,
                "request_key": str(uuid4()),
            },
        )
        print(
            json.dumps(
                {
                    "selected_product": product["name"],
                    "total_paise": quote["total_paise"],
                    "delivery_source": quote["delivery_source"],
                    "review_url": urljoin(args.storefront, quote["review_url"]),
                    "approval_required": quote["approval_required"],
                    "paid": False,
                },
                indent=2,
            )
        )
    except HTTPError as error:
        raise SystemExit(
            f"Merchant returned HTTP {error.code}; no order or payment was created"
        ) from error
    except (ValueError, KeyError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
