from pprint import pprint

from services.company_sync import sync_listed_companies


if __name__ == "__main__":
    pprint(sync_listed_companies())
