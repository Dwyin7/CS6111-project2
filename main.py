# Reference Call:
# python3 project2.py [-spanbert|-gemini] <google api key> <google engine id> <google gemini api key> <r> <t> <q> <k>
import argparse
from googleapiclient.discovery import build


CX = "56f4e4ae2f4944372"  # engine ID
KEY = "AIzaSyDB1xiTbkdr2O8KhnWdHrCJ8jBAfdnxii4"  # Key

GEMINI_KEY = "AIzaSyAg_Arq31eMN18BQI_VcxB_AMinn5ATnBY"


def search_by_query(query, engine_id, engine_key):
    service = build("customsearch", "v1", developerKey=engine_key)
    response = (
        service.cse()
        .list(
            q=query,
            cx=engine_id,
        )
        .execute()
    )
    print(response)
    results = []
    html_result = []
    non_html_idxs = set()

    # log(str(response), p=False)

    # for i, r in enumerate(response["items"]):
    #     if "fileFormat" in r:
    #         log("ahhhhh non-html", False)
    #         non_html_idxs.add(i)
    #     else:
    #         html_result.append(parse_response(r))
    #     results.append(parse_response(r))
    #     # print("html_result", len(html_result))
    # log("Google Search Results:")
    # log("======================")
    return results, html_result, non_html_idxs


def main():
    parser = argparse.ArgumentParser(
        description="Reference implementation for project2"
    )
    parser.add_argument(
        "mode",
        choices=["-spanbert", "-gemini"],
        help="Choose either -spanbert or -gemini",
    )
    parser.add_argument(
        "google_api_key", help="Google Custom Search Engine JSON API Key"
    )
    parser.add_argument("google_engine_id", help="Google Custom Search Engine ID")
    parser.add_argument("google_gemini_api_key", help="Google Gemini API key")
    parser.add_argument(
        "r",
        type=int,
        choices=range(1, 5),
        help="Relation to extract: 1 for Schools_Attended, 2 for Work_For, 3 for Live_In, 4 for Top_Member_Employees",
    )
    parser.add_argument(
        "t",
        type=float,
        help="Extraction confidence threshold (0 to 1); ignored if -gemini",
    )
    parser.add_argument("q", help="Seed query in double quotes")
    parser.add_argument("k", type=int, help="Number of tuples requested in the output")
    args = parser.parse_args()
    mode = args.mode
    google_api_key = args.google_api_key
    google_engine_id = args.google_engine_id
    google_gemini_api_key = args.google_gemini_api_key
    r = args.r
    t = args.t
    q = args.q
    k = args.k
    print("Mode:", mode)
    print("Google API Key:", google_api_key)
    print("Google Engine ID:", google_engine_id)
    print("Google Gemini API Key:", google_gemini_api_key)
    print("Relation:", r)
    print("Threshold:", t)
    print("Seed Query:", q)
    print("Number of Tuples:", k)


if __name__ == "__main__":
    main()
