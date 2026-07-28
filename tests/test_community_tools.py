import json
import os
import unittest
from unittest.mock import patch

import community_tools


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


class CommunityToolsTests(unittest.TestCase):
    def test_sso_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(community_tools.is_ingeschakeld())
            with self.assertRaisesRegex(ValueError, "niet ingeschakeld"):
                community_tools.wissel_ticket("ctt_example")

    def test_valid_ticket_is_exchanged_server_side(self):
        context = {
            "product": {"code": "sermon_processing"},
            "user": {
                "id": "central-user",
                "email": "beheerder@example.nl",
            },
            "organization": {"id": "central-org", "name": "Voorbeeldkerk"},
        }
        environment = {
            "COMMUNITY_TOOLS_SSO_ENABLED": "true",
            "COMMUNITY_TOOLS_URL": "https://communitytools.nl",
            "COMMUNITY_TOOLS_CLIENT_ID": "client-id",
            "COMMUNITY_TOOLS_CLIENT_SECRET": "client-secret",
        }

        with (
            patch.dict(os.environ, environment, clear=True),
            patch("community_tools.urllib.request.urlopen", return_value=_Response(context)) as urlopen,
        ):
            self.assertEqual(community_tools.wissel_ticket("ctt_example"), context)

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://communitytools.nl/api/integrations/exchange",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer client-secret")
        self.assertEqual(request.headers["X-community-tools-client"], "client-id")

    def test_wrong_product_is_rejected(self):
        context = {
            "product": {"code": "gifts_matching"},
            "user": {"id": "central-user", "email": "beheerder@example.nl"},
            "organization": {"id": "central-org"},
        }
        environment = {
            "COMMUNITY_TOOLS_SSO_ENABLED": "true",
            "COMMUNITY_TOOLS_URL": "https://communitytools.nl",
            "COMMUNITY_TOOLS_CLIENT_ID": "client-id",
            "COMMUNITY_TOOLS_CLIENT_SECRET": "client-secret",
        }

        with (
            patch.dict(os.environ, environment, clear=True),
            patch("community_tools.urllib.request.urlopen", return_value=_Response(context)),
        ):
            with self.assertRaisesRegex(ValueError, "Onvolledige"):
                community_tools.wissel_ticket("ctt_example")


if __name__ == "__main__":
    unittest.main()
