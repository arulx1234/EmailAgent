import unittest

import app.api.auth
from oauthlib.oauth2.rfc6749.parameters import parse_token_response


class GoogleOAuthScopeCompatibilityTests(unittest.TestCase):
    def test_accepts_google_token_with_previously_granted_scopes(self):
        response = (
            '{"access_token":"test-token","token_type":"Bearer",'
            '"expires_in":3600,"scope":"openid '
            'https://www.googleapis.com/auth/userinfo.email '
            'https://www.googleapis.com/auth/gmail.modify '
            'https://www.googleapis.com/auth/gmail.readonly '
            'https://www.googleapis.com/auth/gmail.labels"}'
        )

        token = parse_token_response(
            response,
            scope=app.api.auth.SCOPES,
        )

        self.assertIn(
            "https://www.googleapis.com/auth/gmail.modify",
            token["scope"],
        )
        self.assertIn(
            "https://www.googleapis.com/auth/gmail.readonly",
            token["scope"],
        )


if __name__ == "__main__":
    unittest.main()
