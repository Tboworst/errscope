import json

# parses the jsonl file 
def parse_jsonl(filepath):
    # with automatically opens files and cloes even if something goes wrong within the file 
    with open(filepath) as file:
        for line in file:
            #reading one line and loading it we dont want it to be a blob 
            event = json.loads(line)
            #yield returns the value but keeps the function alive up
            yield event
    

if __name__ == "__main__":                                                                                                                      
      for event in parse_jsonl("sample.jsonl"):                                                                                                   
          print(event)