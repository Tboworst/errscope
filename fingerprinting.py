import hashlib
from normalize import normalize_message


def fingerprint(event):
    result = []
    #give a variable name and loop though event we are looking for functions to add
    for frame in event["stack_trace"]:
        result.append(frame["function"])
    
    #this happens once everything is looped through in the list
    function_chain = "->".join(result)