import re
import tokenize

ASSIGNMENT = re.compile("^\s*\w+\s*=")
LABEL = re.compile("^\s*\w+\s*:")

def preprocess(lines):
    data = [(lnr, l.rstrip()) for lnr, l in enumerate(lines)]

    # Handle line continuation.
    no_backslash = []
    while data:
        lnr, l = data.pop(0)

        while l.endswith("\\"):
            l = l[:-1]
            try:
                _, nextl = data.pop(0)
                l += nextl
            except IndexError: break

        no_backslash.append((lnr, l.strip()))

    variables = {}
    instructions = []
    for lnr, l in no_backslash:
        if l.startswith("#") or not l: continue

        ident, rest = re.search("^([a-zA-Z_][a-zA-Z0-9_]+)\s*(.*)", l).groups()
        # Label.
        if rest.startswith(":"):
            rest = rest[1:].lstrip()
            if not (rest.startswith("#") or not rest):
                raise RuntimeError("Trailing characters after label on line {}.".format(lnr + 1))

            variables[ident] = len(instructions)

        # Assignment.





        print(ident, "|", rest)



    




preprocess(open("test.golf"))




