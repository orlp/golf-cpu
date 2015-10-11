#!/usr/bin/env python3

import argparse
import collections
import golf
import idata
import io
import json
import os
import re
import string
import struct
import sys
import tokenize
import math
import inspect

class SyntaxError(Exception):
    # Hide __main__.
    __module__ = Exception.__module__

class Label:
    def __init__(self, instr_nr, name):
        self.instr_nr = instr_nr
        self.name = name

    def __repr__(self):
        return "Label({!r}, {!r})".format(self.instr_nr, self.name)


class Reg:
    def __init__(self, reg):
        self.reg = reg

    def __repr__(self):
        return "Reg({!r})".format(self.reg)

class Instr:
    def __init__(self, debug_line, instr, args):
        self.debug_line = debug_line
        self.instr = instr
        self.args = args

    def size(self):
        if self.instr == "ret": return 4

        n = 4
        for arg in self.args:
            if   isinstance(arg, Reg):   n += 0
            elif isinstance(arg, Label): n += 4
            elif            arg == 0:    n += 0
            elif   -2**7 <= arg <  2**7: n += 1
            elif  -2**15 <= arg < 2**15: n += 2
            elif  -2**31 <= arg < 2**31: n += 4
            elif  -2**63 <= arg < 2**64: n += 8
            else: assert(False)

        return n

    def encode(self):
        instr_id = idata.instr_ids[self.instr]

        if self.instr == "ret":
            regs = {reg.reg for reg in self.args}
            instr_bits = ["1" if reg in regs else "0" for reg in string.ascii_lowercase[:-1]]
            instr_flag = int("".join(instr_bits)[::-1], 2)

            return struct.pack("<I", instr_id | (instr_flag << 7))

        immediates = b""
        flags = []
        for arg in self.args:
            if isinstance(arg, Reg):
                flags.append(5 + string.ascii_lowercase.index(arg.reg))
            elif isinstance(arg, Label):
                flags.append(3)
                immediates += struct.pack("<i", arg.offset)
            elif arg == 0:
                flags.append(0)
            elif -2**7 <= arg <  2**7:
                flags.append(1)
                immediates += struct.pack("<b", arg)
            elif  -2**15 <= arg < 2**15:
                flags.append(2)
                immediates += struct.pack("<h", arg)
            elif  -2**31 <= arg < 2**31:
                flags.append(3)
                immediates += struct.pack("<i", arg)
            elif  -2**63 <= arg < 2**64:
                flags.append(4)
                if arg < 0: immediates += struct.pack("<q", arg)
                else: immediates += struct.pack("<Q", arg)
            else: assert(False)

        instr_flag = 0
        for flag in flags[::-1]:
            instr_flag <<= 5
            instr_flag |= flag

        return struct.pack("<I", instr_id | (instr_flag << 7)) + immediates

    def __repr__(self):
        return "Instr({!r}, {!r}, {!r})".format(self.debug_line, self.instr, self.args)

class Data:
    def __init__(self, data):
        self.data = data

        if (not (isinstance(data, str) or isinstance(data, bytes)) and
                 isinstance(data, collections.Iterable)):
            self.data = tuple(data)

    def encode(self):
        if isinstance(self.data, bytes):
            return self.data

        if isinstance(self.data, str):
            return self.data.encode("utf-8") + b"\x00"

        return b"".join(struct.pack("<Q", n & 0xffffffffffffffff) for n in self.data)

    def __repr__(self):
        return "Data({!r})".format(self.data)


def check_instr_arguments(instr, args, lnr, lines):
    """Checks if an instruction is valid, and whether its arguments are valid."""

    if instr == "ret":
        if not all(isinstance(op, Reg) for op in args):
            raise SyntaxError(
                "Not all arguments to ret are registers on line {}:\n{}"
                .format(lnr + 1, lines[lnr]))

        if any(reg.reg == "z" for reg in args):
            print(
                "Warning: unnecessary z passed into ret on line {}:\n{}"
                .format(lnr + 1, lines[lnr]))

        return

    if instr not in idata.instr_signatures:
        raise SyntaxError(
            "Unknown instruction '{}' on line {}:\n{}"
            .format(instr, lnr + 1, lines[lnr]))

    sig = idata.instr_signatures[instr]

    if sum(sig) != len(args):
        raise SyntaxError(
            "Wrong amount of arguments for '{}' on line {}:\n{}"
            .format(instr, lnr + 1, lines[lnr]))

    if not all(isinstance(op, Reg) for op in args[:sig[0]]):
        raise SyntaxError(
            "'{}' requires {} output register(s) on line {}:\n{}"
            .format(instr, sig[0], lnr + 1, lines[lnr]))

    if not all(isinstance(op, Reg) or isinstance(op, Label) or isinstance(op, Data) or
               (isinstance(op, int) and -2**63 <= op < 2**64) for op in args):
        raise SyntaxError(
            "Not all arguments are 64 bit integers, registers or labels on line {}:\n{}"
            .format(lnr + 1, lines[lnr]))

    for op in args:
        if isinstance(op, Data):
            if not (isinstance(op.data, str) or isinstance(op.data, bytes) or
                    (isinstance(op.data, collections.Iterable) and
                        all(isinstance(n, int) and -2**63 <= n < 2**64 for n in op.data))):
                raise SyntaxError(
                    "data() argument is not valid on line {}:\n{}"
                    .format(lnr + 1, lines[lnr]))

    if instr == "sz" or instr == "snz":
        if not isinstance(args[1], int):
                raise SyntaxError(
                    "number of instructions to skip not a constant integer on line {}:\n{}"
                    .format(lnr + 1, lines[lnr]))




def translate_pseudo_instr(instr_nr, instr, args):
    """Turns an instruction and a list of arguments into a list of pairs of instructions and lists
    of arguments, without pseudo instructions."""

    if instr in {"ge", "geq", "geu", "gequ"}:
        return [["le" + instr[2:], args[:1] + args[1:][::-1]],]

    elif instr == "mov":
        return [["add", [args[0], args[1], 0]],]

    elif instr in {"inc", "dec"}:
        addends = {
            "inc": 1,
            "dec": -1,
        }

        return [["add", [args[0], args[0], addends[instr]]],]

    elif instr == "neg":
        return [["sub", [args[0], 0, args[0]]],]

    elif instr == "jmp":
        return [["jz", [args[0], 0]],]

    elif instr == "sz":
        return [["jz", [Label(instr_nr + args[1] + 1, None), args[0]]],]

    elif instr == "snz":
        return [["jnz", [Label(instr_nr + args[1] + 1, None), args[0]]],]

    elif instr == "push":
        return [["sw", [args[0], args[1]]], ["add", [args[0], args[0], 8]]]

    elif instr == "pop":
        return [["sub", [args[1], args[1], 8]], ["lw", [args[0], args[1]]]]

    return [[instr, args],]


def preprocess(lines):
    lines = [l.rstrip() for l in lines]
    data = [(lnr, l) for lnr, l in enumerate(lines)]

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

    variables = dict(mem for mem in inspect.getmembers(math) if not mem[0].startswith("_"))
    variables.update({c: Reg(c) for c in string.ascii_lowercase})
    variables["pow"] = pow
    variables["math"] = math
    variables["data"] = Data
    num_instructions = 0

    # Label pass.
    for lnr, l in no_backslash:
        if l.startswith("#") or not l: continue

        parse = re.search("^([a-zA-Z_][a-zA-Z0-9_]+)\s*(.*)", l)
        if parse is None:
            raise SyntaxError("Syntax error on line {}:\n{}".format(lnr + 1, lines[lnr]))

        ident, rest = parse.groups()
        if rest.startswith(":"):
            rest = rest[1:].lstrip()
            if not (rest.startswith("#") or not rest):
                raise SyntaxError(
                    "Trailing characters after label on line {}:\n{}".format(lnr + 1, lines[lnr]))

            if ident in variables and isinstance(variables[ident], Label):
                raise SyntaxError(
                    "Duplicate label name on line {}:\n{}".format(lnr + 1, lines[lnr]))

            variables[ident] = Label(num_instructions, ident)

        elif not rest.startswith("="):
            num_instructions += 1

    # Read instructions and assignments.
    instructions = []
    for lnr, l in no_backslash:
        if l.startswith("#") or not l: continue

        # Syntax already checked last time.
        ident, rest = re.search("^([a-zA-Z_][a-zA-Z0-9_]+)\s*(.*)", l).groups()

        # Strip comments (reuse Python's tokenizer to correctly handle comments in strings, etc).
        tokens = tokenize.tokenize(io.BytesIO(rest.encode("utf-8")).readline)
        stripped_tokens = []
        for typ, tok, _, _, _  in tokens:
            if typ == tokenize.COMMENT: continue
            stripped_tokens.append((typ, tok))
        rest = tokenize.untokenize(stripped_tokens).decode("utf-8")

        # Assignment.
        if rest.startswith("="):
            if ident in variables and isinstance(variables[ident], Label):
                raise SyntaxError(
                    "Overwriting label name on line {}:\n{}".format(lnr + 1, lines[lnr]))

            variables[ident] = eval(rest[1:], variables)

        # Instruction.
        elif not rest.startswith(":"):
            args = list(eval("(None, {})".format(rest), variables)[1:])
            check_instr_arguments(ident, args, lnr, lines)
            instructions.append(Instr(lnr, ident, args))

    return instructions


def assemble(lines):
    instructions = preprocess(lines)

    data_segment = b""
    data_offsets = {}

    # Data substitution pass.
    for instr in instructions:
        for i, arg in enumerate(instr.args):
            if isinstance(arg, Data):
                if arg.data not in data_offsets:
                    offset = len(data_segment)
                    data_segment += arg.encode()
                    data_offsets[arg.data] = offset + 0x2000000000000000

                instr.args[i] = data_offsets[arg.data]

    # Translate pseudo-instructions.
    instr_nrs = {}
    n = 0
    no_pseudo = []
    for instr_nr, instr in enumerate(instructions):
        instr_nrs[instr_nr] = n
        for name, args in translate_pseudo_instr(instr_nr, instr.instr, instr.args):
            no_pseudo.append(Instr(instr.debug_line, name, args))
            n += 1

    # Label substitution pass.
    offsets = [0]
    for instr in no_pseudo:
        offsets.append(offsets[-1] + instr.size())

    labels = {}
    for instr in no_pseudo:
        for i, arg in enumerate(instr.args):
            if isinstance(arg, Label):
                arg.offset = offsets[instr_nrs[arg.instr_nr]]
                if arg.name: labels[arg.name] = arg.offset

    # Encode instructions.
    instr_stream = b""
    debug = {}
    for instr in no_pseudo:
        debug[len(instr_stream)] = instr.debug_line
        instr_stream += instr.encode()

    debug["labels"] = labels

    return struct.pack("<I", len(data_segment)) + data_segment + instr_stream, debug


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GOLF assembler.")
    parser.add_argument("file", help="source file")
    parser.add_argument("-r", dest="run", action="store_true",
                        help="don't produce a binary, run source directly")
    parser.add_argument("-o", metavar="file", help="output file")
    parser.add_argument("-d", metavar="file", help="debug file")
    parser.set_defaults(run=False)

    args = parser.parse_args()
    if args.o is None: args.o = os.path.splitext(args.file)[0] + ".bin"
    if args.d is None: args.d = os.path.splitext(args.file)[0] + ".dbg"

    with open(args.file) as in_file:
        lines = [l.rstrip() for l in in_file]

    binary, debug = assemble(lines)

    if args.run:
        sys.exit(golf.GolfCPU(binary).run())
    else:
        debug["lines"] = lines
        with open(args.o, "wb") as out_file: out_file.write(binary)
        with open(args.d, "w") as dbg_file: json.dump(debug, dbg_file)
