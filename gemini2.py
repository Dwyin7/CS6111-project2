from collections import defaultdict
import os
import google.api_core.exceptions
import google.generativeai as genai
import spacy
import json
import time

#input
    # 1.prompt, with example
    # 2.context
    # 3.results = X
    #initialize a generative model
relation_name = {
        0:"Schools_attended",
        1:"Work_For",
        2:"Live_in",
        3:"Top_Member_Employees",
    }

label  ={
        0: ["PERSON",{"ORG"}],
        1: ["PERSON",{"ORG"}],
        2: ["PERSON",{"GPE", "LOC"}],
        3: ["ORG",{"PERSON"}],
    }

#generage prompt with task sentence and few shot(<5) from extracted result
def generate_prompt(relation_index,X, sentence, init_query):
    restriction ={
        0: ["'Person'","'Organization'"],
        1: ["'Person'","'Organization'"],
        2: ["'Person'","one of 'LOCATION', 'CITY', 'STATE_OR_PROVINCE', or 'COUNTRY'"],
        3: ["'Organization'","'Person'"],
    }

    definition ={
        0: f"a Subject (label = {restriction[0][0]}) has attended Object (label = {restriction[0][1]}) for education.",
        1: f"a Subject (label = {restriction[1][0]}) is employed by or works for an Object (label = {restriction[1][1]})",
        2: f"a Subject (label = {restriction[2][0]}) has lived in Object (label = {restriction[2][1]})",
        3: f"an Object (label = {restriction[3][1]}) is a top member or employee of an Subject (label = {restriction[3][0]})",
    }
    
    # max shot = 5, value 1 = explicit relationship
    # + can consider the first query..
    shot =0
    example =""
    for key in X:
        if(X[key] ==1 and shot <5):
            example = f"""; {key[0]}, {key[2]}"""
            shot +=1

    prompt = f'''
    Task: Identify entities labeled as {restriction[relation_index][0]} and {restriction[relation_index][1]} and analyze the relations between those entities to extract all implicit or explicit {relation_name[relation_index]} relations in the sentence.
    sentence : {sentence}
    Definition: A {relation_name[relation_index]} relation indicates that {definition[relation_index]}.
    Return format: a json format, this JSON object will contain a series of key-value pairs, where each key is a sequential number starting from 0 and incrementing by 1 for each identified relationship (i.e., 0, 1, 2, ..., n). 
    The value for each key will be another JSON object that describes a single instance of the specified relationship type. The format for each relationship JSON object is {{ "Subj": Subject, "Obj": Object }},
    * From now on, return the output as a json string without newline symbol
    * Include all identified relationships in the json.
    * if there is no relationshop exists return empty json without newline symbol.
    * Both subject an object are proper nouns, not pronouns.
    '''
    
    return prompt

#get gemini return 
def get_gemini_completion(GEMINI_KEY, prompt, model_name, max_tokens, temperature, top_k, top_p):
    #apply api key
    #GEMINI_KEY = "AIzaSyArX0np_auOKj09EGr0OKz8hos0BoM06cs" #GapiKey
    genai.configure(api_key=GEMINI_KEY)

    # Initialize a generative model
    model =  genai.GenerativeModel(model_name)

    # Configure the model with desired parameters
    generation_config=genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k
    )
    
    
    # Generate a response
    try:
        response = model.generate_content(prompt, generation_config=generation_config)
    except google.api_core.exceptions.ResourceExhausted as e:
        #retry after 10 seconds
        print("google.api_core.exceptions.ResourceExhausted wait 10s retry again")
        time.sleep(10)
        return get_gemini_completion(GEMINI_KEY, prompt, model_name, max_tokens, temperature, top_k, top_p)
    print(response, "response")

    return response.text

def gemini(GEMINI_KEY, relation_index, X, content, init_query, label_dict):

    #get prompt
    prompt = generate_prompt(relation_index, X, content, init_query)

    #get_gemini_completion
    #gemini model specify
    model_name ="gemini-1.0-pro"
    max_tokens =  1000 #0-8192
    temperature = 0.4 #more deterministic, 0-1
    top_k = 32 #next-token can,1-40, default =32
    top_p = 1 #select culm threshold, 0-1, default =1

    # get candidate
    print(prompt)
    extracted_string= get_gemini_completion(GEMINI_KEY, prompt, model_name, max_tokens, temperature, top_k, top_p)
    if extracted_string == "{}":
        return X
    # print(label_dict, "::::::::")
    
    # 
    # print(type(extracted_string),extracted_string,"extract json")
    # print(extracted_string)
    extracted_json = json.loads(extracted_string)
    def dict_to_list(d):
        r = [(v['Subj'],v['Obj']) for _,v in d.items()]
        return r
    print(dict_to_list(extracted_json))
    extracted_pairs = dict_to_list(extracted_json)
    # while(not validate_relationship_format(extracted_string)):
    #       new_prompt = validate_relationship_format(extracted_string)
    #       print(new_prompt)
    #       extracted_string= get_gemini_completion(new_prompt, model_name, max_tokens, 0.1, top_k, top_p)

    
    #process cand verify cand. then store into X 
    # lines = extracted_string.split('\n')
    for elements in extracted_pairs:
        # if (label_dict[elements[0]] == label[relation_index][0]) and (label_dict[elements[1]] in label[relation_index][1]):
        X[(elements[0], relation_name[relation_index], elements[1])] = 1
        print("\n\t\t=== Extracted Relation ===")
        print("\t\tRelation: {} \nSubject: {}\tObject: {}".format(relation_name[relation_index], elements[0], elements[1]))
        
    # for line in lines:
    #     clean_line = line.strip('- ').strip('[]')
    #     elements = [element.strip( ).strip('"') for element in clean_line.split(',')]
    #     # print(elements[0], label_dict[elements[0]], label[relation_index][0])

    #     if (label_dict[elements[0]] == label[relation_index][0]) and (label_dict[elements[1]] in label[relation_index][1]):
            
    #         X[(elements[0], relation_name[relation_index], elements[1])] = 1

    #         print("\n\t\t=== Extracted Relation ===")
    #         print("\t\tRelation: {} \nSubject: {}\tObject: {}".format(relation_name[relation_index], elements[0], elements[1]))
    
    return X

def validate_relationship_format(relationship_str):
    # Check if string starts with '[' and ends with ']'
    if not (relationship_str.startswith("[") and relationship_str.endswith("]")):
        return f"""Result does not start and end with brackets. Correct {relationship_str} in [Subject,Object] format"""

    # Remove brackets and split by comma
    content = relationship_str[1:-1].split(",")
    if len(content) != 2:
        return f"""Result does not contain exactly two elements. Correct {relationship_str} in [Subject,Object] format"""

    return True    

def main(): 
    sentence = "Zuckerberg attended Harvard University, where he launched the Facebook social networking service from his dormitory room on February 4, 2004, with college roommates Eduardo Saverin, Andrew McCollum, Dustin Moskovitz, and Chris Hughes. Bill Gates stepped down as chairman of Microsoft in February 2014 and assumed a new post as technology adviser to support the newly appointed CEO Satya Nadella. "
    nlp = spacy.load("en_core_web_lg")
    doc = nlp(sentence)
    
    label_dict ={}
    for ent in doc.ents:
        label_dict[ent.text] = ent.label_
    
    # print(label_dict["Bill Gates"])

    X = defaultdict(int)
    #X[('Bill Gates','', 'Microsoft')] = 1
    init_query = f"""megan rapinoe redding"""
    GEMINI_KEY = "AIzaSyArX0np_auOKj09EGr0OKz8hos0BoM06cs"
    # Schools_Attended: Subject: PERSON, Object: ORGANIZATION 1
    # Work_For: Subject: PERSON, Object: ORGANIZATION 2
    # Live_In: Subject: PERSON, Object: one of LOCATION, CITY, STATE_OR_PROVINCE, or COUNTRY 3
    # Top_Member_Employees: Subject: ORGANIZATION, Object: PERSON 4
    extracted_tuples = gemini(GEMINI_KEY,1, X, sentence,init_query,label_dict)
    print(extracted_tuples)



if __name__ == "__main__":
    main()



'''
    Task: Identify entities labeled as "Person" and "Organization"and analyze the relationships between those entities to extract **Work_For** relationships in the sentence. 

    sentence: "Bill Gates stepped down as chairman of Microsoft in February 2014 and assumed a new post as technology adviser to support the newly appointed CEO Satya Nadella."

    Definition: A "Work_For" relationship indicates that a Subject(label = person) is employed by or works for an Object(label= organization).
    Output format: Return a list of lists, , where each list represents a Work_For relationship tuple in the following format: [Subject, Object, exp/imp].
    * The third column indicates whether the tuple is **explicitly (exp)** or **implicitly (imp)** implied by the sentence. 
    * Include all identified relationships in separate tuples.
    * Only include outputs which Subject is label as 'Person' and Object is label as 'Organization''. 
'''