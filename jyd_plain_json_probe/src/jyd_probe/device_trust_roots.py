"""Release-owned public trust configuration, compiled into the backend.

This file contains PUBLIC P-256 keys only. Server and device private keys must
never be added here or read from mutable client configuration.
"""

TRUSTED_ISSUERS: tuple[dict, ...] = ({'environment': 'production',
  'keys': [{'jwk': {'crv': 'P-256',
                    'kty': 'EC',
                    'x': 'W_BdOGkTzjP97AKjeT46c0TMHGwU1oDMkEaYbXOsZOI',
                    'y': 'DNY4ye2Wx94bbuEZUqybYFULVqS6R184P6VveDuvFDI'},
            'kid': 'production-20260901-01'}],
  'origin': 'https://video.lanyingjk01.com'},)
