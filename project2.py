# Reference Call:
# python3 project2.py [-spanbert|-gemini] <google api key> <google engine id> <google gemini api key> <r> <t> <q> <k>


# e.g.
# python3 project2.py -spanbert "AIzaSyBdPoK9zbUZXnDHG4LMMu972zSH7nGdnM8" "56f4e4ae2f4944372" "123" 2 0.7 "bill gates microsoft" 10
import argparse
from googleapiclient.discovery import build
import sys
from bs4 import BeautifulSoup
import requests
import spacy
from SpanBERT.spanbert import SpanBERT
from SpanBERT.spacy_help_functions import *


nlp = spacy.load("en_core_web_lg")


spanbert = None
CX = "56f4e4ae2f4944372"  # engine ID
KEY = "AIzaSyBdPoK9zbUZXnDHG4LMMu972zSH7nGdnM8"  # Key

GEMINI_KEY = "AIzaSyAg_Arq31eMN18BQI_VcxB_AMinn5ATnBY"

relation_map = {
        0:"per:schools_attended",
        1:"per:employee_of",
        2:"per:cities_of_residence",
        3:"org:top_members/employees",
    }
target_relation = ""

headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
        'DNT': '1',  # Do Not Track Request Header
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }


def parse_response(response):
    """title, URL, and description"""
    r = {}
    r["title"] = response["title"]
    r["url"] = response["link"]
    if "snippet" in response:
        r["summary"] = response["snippet"]
    else:
        r["summary"] = None
    return r


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
    results = []
    html_result = []
    non_html_idxs = set()

    for i, r in enumerate(response["items"]):
        if "fileFormat" in r:
            non_html_idxs.add(i)
        else:
            html_result.append(parse_response(r))
        results.append(parse_response(r))
    # print(results)
    return results, html_result, non_html_idxs


def page_extraction(url):
    print(f"{url}")
    try:
        response = requests.get(url=url,headers=headers, timeout=60)  # timeout 60s
        if response.status_code != 200:
            print(f"Request to {url} failed with status code {response.status_code}")
            return None, False
    except Exception as e:
        print(e)
        return None, False
    soup = BeautifulSoup(response.text, 'html.parser')
    # for script_or_style in soup(["script", "style"]):
    #     script_or_style.decompose()
    # text = soup.get_text(' ', strip=True)
    
    # main_content = soup.find('article') or soup.find('main') or soup.find_all('div', recursive=True)
    # text = ' '.join([mc.get_text(' ', strip=True) for mc in main_content]) if isinstance(main_content, list) else main_content.get_text(' ', strip=True)

    for script in soup(["script", "style"]):
        script.extract()    # rip it out
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)

    print(f"Webpage length (num characters): {len(text)}")
    # truncate if necessary
    if len(text) > 10000:
        print(f"Trimming webpage content from {len(text)} to {10000} characters")
        text = text[:10000]
    # raw_text = "Zuckerberg attended Harvard University, where he launched the Facebook social networking service from his dormitory room on February 4, 2004, with college roommates Eduardo Saverin, Andrew McCollum, Dustin Moskovitz, and Chris Hughes. Bill Gates stepped down as chairman of Microsoft in February 2014 and assumed a new post as technology adviser to support the newly appointed CEO Satya Nadella. "
    # return raw_text, True
    # print(text)
    return text, True


    



def information_extraction(url, relation_index,mode,conf,acc):
    # method: [-spanbert|-gemini]
    content,ok = page_extraction(url)
    if not ok:
        return 
    doc = nlp(content)
    #spanbert for doc
    if mode == "-spanbert":
        SB(doc,relation_index,conf,acc)
    # gemini
    return




def SB(doc, relation_index, conf,acc):
    global spanbert

    entity_of_interests_lst = [("PERSON","ORGANIZATION"),("PERSON","ORGANIZATION"),("PERSON","LOCATION","CITY","STATE_OR_PROVINCE","COUNTRY"),("ORGANIZATION","PERSON")]
    
    entities_of_interest = entity_of_interests_lst[relation_index]
    sub = entity_of_interests_lst[relation_index][0]
    obj = set(entity_of_interests_lst[relation_index][1:])
    # res = acc #ref
    ext_ct = 0
    ext_st_ct = 0
    print(f"Extracted {len(list(doc.sents))} sentences. Processing each sentence one by one to check for presence of right pair of named entity types; if so, will run the second pipeline ...")
    for i,sentence in enumerate(doc.sents):
        # ents = get_entities(sentence, entities_of_interest)
        flag = False
        if (i+1)%5 == 0:
            print(f"Processed {i+1} / {len(list(doc.sents))} sentences")
        candidate_pairs = []
        sentence_entity_pairs = create_entity_pairs(sentence, entities_of_interest)
        for ep in sentence_entity_pairs:
            # TODO: keep subject-object pairs of the right type for the target relation (e.g., Person:Organization for the "Work_For" relation)
            e1,e2 = ep[1],ep[2]
            if e1[1] == sub and e2[1] in obj:
                candidate_pairs.append({"tokens": ep[0], "subj": ep[1], "obj": ep[2]})
            if e2[1] == sub and e1[1] in obj:
                candidate_pairs.append({"tokens": ep[0], "subj": ep[2], "obj": ep[1]})

        if len(candidate_pairs) == 0:
            continue
        
        # print("Applying SpanBERT for each of the {} candidate pairs. This should take some time...".format(len(candidate_pairs)))
        relation_preds = spanbert.predict(candidate_pairs)  # get predictions: list of (relation, confidence) pairs
        # print("\nExtracted relations:")
        for ex, pred in list(zip(candidate_pairs, relation_preds)):
            relation = pred[0]
            if relation == 'no_relation' or relation != relation_map[relation_index]:
                continue
            print("\n\t\t=== Extracted Relation ===")
            print("\t\tTokens: {}".format(ex['tokens']))
            subj = ex["subj"][0]
            obj = ex["obj"][0]
            confidence = pred[1]
            print("\t\tRelation: {} (Confidence: {:.3f})\nSubject: {}\tObject: {}".format(relation, confidence, subj, obj))
            if confidence > conf:
                if acc[(subj, relation, obj)] < confidence:
                    acc[(subj, relation, obj)] = confidence
                    print("\t\tAdding to set of extracted relations")
                    ext_ct += 1
                    flag = True
                else:
                    print("\t\tDuplicate with lower confidence than existing record. Ignoring this.")
            else:
                print("\t\tConfidence is lower than threshold confidence. Ignoring this.")
            print("\t\t==========")
        if flag:
            ext_st_ct += 1
    print(f"Extracted annotations for  {ext_st_ct}  out of total  {len(list(doc.sents))}  sentences")
    print(f"Relations extracted from this website: {ext_ct} (Overall: {len(acc.keys())})")
    return acc



def ISE(query, mode, relation_index,conf,k, engine_id, engine_key):
    # iterative set expansion
    X = defaultdict(int) #(sub,relation,obj): conf
    seen_url = set()
    used_query = set()
    used_query.add(query)
    #load pretrained
    global spanbert
    if mode == "-spanbert":
        spanbert = SpanBERT("./SpanBERT/pretrained_spanbert")  
    cur_query = query
    iter_count = 1
    while len(X.keys()) < k:
        print(f"=========== Iteration: {iter_count} - Query: {cur_query} =============")
        iter_count += 1

        result, _, _ = search_by_query(cur_query, engine_id, engine_key)
        for i,r in enumerate(result):
            url = r['url']
            if url in seen_url:
                continue
            seen_url.add(url)
            #process url
            print(f"URL ({i+1}/10) :")
            information_extraction(url,relation_index,mode,conf,X)
            
        print_pretty_relations(X)
        
        #generate new query
        top = 0
        ord_candidate_tuples = sorted(X.items(), key= lambda x: x[1], reverse=True)
        candidate_query = f"{ord_candidate_tuples[top][0][0]} {ord_candidate_tuples[top][0][2]}"
        while candidate_query in used_query:
            top += 1
            candidate_query = f"{ord_candidate_tuples[top][0][0]} {ord_candidate_tuples[top][0][2]}"
            if top >= len(ord_candidate_tuples):
                raise "should not happen"
        cur_query = candidate_query
        used_query.add(cur_query)

    
    print(X,"resultx", len(X.keys()))
    
    #return top k
    ord_candidate_tuples = sorted(X.items(), key= lambda x: x[1], reverse=True)  


def print_pretty_relations(X):
    global target_relation
    sorted_relations = sorted(X.items(), key=lambda item: item[1], reverse=True)
    print("="*80)
    print(f"ALL RELATIONS for {target_relation} ({len(sorted_relations)})")
    print("="*80)

    for ((subject, _, obj), confidence) in sorted_relations:
        print("Confidence: {:.7f} \t| Subject: {} \t| Object: {}".format(confidence, subject, obj))

def main():
    if len(sys.argv) != 9:  # Check if the correct number of arguments are provided
        print(
            "Usage: <mode> <google_api_key> <google_engine_id> <google_gemini_api_key> <r> <t> <q> <k>"
        )
        sys.exit(1)

    mode = sys.argv[1]
    google_api_key = sys.argv[2]
    google_engine_id = sys.argv[3]
    google_gemini_api_key = sys.argv[4]
    r = int(sys.argv[5])
    t = float(sys.argv[6])
    q = sys.argv[7]
    k = int(sys.argv[8])
    global spanbert
    global target_relation
    target_relation = relation_map[r-1]

    print("Mode:", mode)
    print("Google API Key:", google_api_key)
    print("Google Engine ID:", google_engine_id)
    print("Google Gemini API Key:", google_gemini_api_key)
    print("Relation:", relation_map[r-1]) #1-4
    print("Threshold:", t)
    print("Seed Query:", q)
    print("Number of Tuples:", k)
    ISE(q,mode,r-1,t,k, google_engine_id, google_api_key)


if __name__ == "__main__":
    main()
