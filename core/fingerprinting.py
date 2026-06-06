import hashlib
from .normalize import normalize_message


def fingerprint(event):
    result = []
    #give a variable name and loop though event we are looking for functions to add
    for frame in event["stack_trace"]:
        result.append(frame["function"])
    
    #this happens once everything is looped through in the list
    function_chain = "->".join(result)

    service = event.get("service") or "unknown"
    environment = event.get("environment") or "unknown"

    fingerprint_str = service+"|"+environment+"|"+event["exception_type"]+"|"+normalize_message(event["message"])+"|"+function_chain
    #hashing this message so that we can pair it with other messages
    return hashlib.md5(fingerprint_str.encode()).hexdigest()
