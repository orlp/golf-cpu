import sys
import struct
import idata
import string
import random
import argparse

class GolfCPU:
    def __init__(self, binary):
        data_len = struct.unpack_from("<I", binary)[0]
        self.data = binary[4:4+data_len]
        self.instructions = binary[4+data_len:]
        self.isp = 0
        self.regs = {k: 0 for k in string.ascii_lowercase}
        self.regs["z"] = 0x1000000000000000
        self.callstack = []
        self.stack = []
        self.heap = []
        self.cycle_count = 0

    def unpack_imm(self, fmt):
        r = struct.unpack_from("<" + fmt, self.instructions, self.isp)[0]
        self.isp += struct.calcsize(fmt)
        return r

    # n-bit two's complement int to int.
    def twos(self, x, n=64):
        if x & (1 << (n - 1)): x = x - (1 << n)
        return x

    # Unsigned wrapping, int to two's complement.
    def u(self, x):
        return x & ((1 << 64) - 1) 

    def shl(self, a, b):
        b = self.twos(b)
        if b < 0: return a >> -b
        return a << b

    def shr(self, a, b):
        return self.shl(a, self.u(-self.twos(b)))

    def sar(self, a, b):
        a = self.twos(a)
        return self.u(self.shr(a, b))
    
    def mul(self, a, b):
        return self.mulu(self.twos(a), self.twos(b))

    def mulu(self, a, b):
        r = (a * b) & ((1 << 128) - 1)
        return self.u(r), r >> 64

    def div(self, a, b):
        a, b = self.twos(a), self.twos(b)
        quo, rem = a // b, a % b
        return self.u(quo), self.u(rem)

    def divu(self, a, b):
        quo, rem = a // b, a % b
        return quo, rem

    def load(self, a, width):
        if a == 0xffffffffffffffff:
            if width != 8: raise RuntimeError("May only use lw/sw for stdin/stdout.")
            r = ord(sys.stdin.read(1))
            return r or self.u(-1)

        if a >= 0x2000000000000000:
            a = a - 0x2000000000000000
            r = self.data[a:a+width]
        elif a >= 0x1000000000000000:
            a = a - 0x1000000000000000
            r = self.stack[a:a+width]
        else:
            r = self.heap[a:a+width]

        fmts = {1: "B", 2: "S", 4: "I", 8: "Q"}
        return struct.unpack("<" + fmts[width], bytes(r))[0]

    def store(self, a, b, width):
        if a == 0xffffffffffffffff:
            if width != 8: raise RuntimeError("May only use lw/sw for stdin/stdout.")
            sys.stdout.write(chr(b & 0xff))
            sys.stdout.flush()
            return
        
        fmts = {1: "B", 2: "S", 4: "I", 8: "Q"}
        b = struct.pack("<" + fmts[width], b & ((1 << (8*width)) - 1))
        if a >= 0x2000000000000000:
            raise RuntimeError("Attempt to store in read-only data section.")
        elif a >= 0x1000000000000000:
            a = a - 0x1000000000000000
            if len(self.stack) < a + width:
                self.stack += [0] * (a + width - len(self.stack))
            self.stack[a:a+width] = b
        else:
            if len(self.heap) < a + width:
                self.heap += [0] * (a + width - len(self.heap))
            self.heap[a:a+width] = b

    def execute_instr(self, instr, args):
        if instr == "ret":
            if not self.callstack:
                raise RuntimeError("Return executed while callstack is empty.")

            old_isp, old_regs = self.callstack.pop()
            old_regs.update({k: self.regs[k] for k in args})
            self.isp = old_isp
            self.regs = old_regs
            return

        # Look up register values.
        for i in range(idata.instr_signatures[instr][0], len(args)):
            if isinstance(args[i], str):
                args[i] = self.regs[args[i]]

        if instr == "not":  self.regs[args[0]] = int(not args[1])
        elif instr == "or":   self.regs[args[0]] = args[1] | args[2]
        elif instr == "xor":  self.regs[args[0]] = args[1] ^ args[2]
        elif instr == "and":  self.regs[args[0]] = args[1] & args[2]
        elif instr == "shl":  self.regs[args[0]] = self.shl(args[1], args[2])
        elif instr == "shr":  self.regs[args[0]] = self.shr(args[1], args[2])
        elif instr == "sar":  self.regs[args[0]] = self.sar(args[1], args[2])
        elif instr == "add":  self.regs[args[0]] = self.u(args[1] + args[2])
        elif instr == "sub":  self.regs[args[0]] = self.u(args[1] - args[2])
        elif instr == "cmp":  self.regs[args[0]] = int(args[1] == args[2])
        elif instr == "neq":  self.regs[args[0]] = int(args[1] != args[2])
        elif instr == "le":   self.regs[args[0]] = int(self.twos(args[1]) <  self.twos(args[2]))
        elif instr == "leq":  self.regs[args[0]] = int(self.twos(args[1]) <= self.twos(args[2]))
        elif instr == "leu":  self.regs[args[0]] = int(args[1] <  args[2])
        elif instr == "lequ": self.regs[args[0]] = int(args[1] <= args[2])
        elif instr == "mul":  self.regs[args[0]], self.regs[args[1]] = self.mul(args[2], args[3])
        elif instr == "mulu": self.regs[args[0]], self.regs[args[1]] = self.mulu(args[2], args[3])
        elif instr == "div":  self.regs[args[0]], self.regs[args[1]] = self.div(args[2], args[3])
        elif instr == "divu": self.regs[args[0]], self.regs[args[1]] = self.divu(args[2], args[3])
        elif instr == "lb":   self.regs[args[0]] = self.u(self.twos(self.load(args[1], 1), 8))
        elif instr == "lbu":  self.regs[args[0]] = self.load(args[1], 1)
        elif instr == "ls":   self.regs[args[0]] = self.u(self.twos(self.load(args[1], 2), 16))
        elif instr == "lsu":  self.regs[args[0]] = self.load(args[1], 2)
        elif instr == "li":   self.regs[args[0]] = self.u(self.twos(self.load(args[1], 4), 32))
        elif instr == "liu":  self.regs[args[0]] = self.load(args[1], 4)
        elif instr == "lw":   self.regs[args[0]] = self.load(args[1], 8)
        elif instr == "sb":   self.store(args[0], args[1], 1)
        elif instr == "ss":   self.store(args[0], args[1], 2)
        elif instr == "si":   self.store(args[0], args[1], 4)
        elif instr == "sw":   self.store(args[0], args[1], 8)
        elif instr == "rand": self.regs[args[0]] = random.randrange(1 << 64)
        elif instr == "jz":   self.isp = args[0] if not args[1] else self.isp
        elif instr == "jnz":  self.isp = args[0] if     args[1] else self.isp
        elif instr == "call":
            self.callstack.append((self.isp, self.regs.copy()))
            self.isp = args[0]
        else: assert(False)

        self.cycle_count += idata.cycle_counts[instr]

    def run(self):
        while self.isp < len(self.instructions):
            instr = self.unpack_imm("I")
            instr_id = instr & 0x7f
            instr_flags = instr >> 7
            instr_args = []
            instr_name = idata.instr_names[instr_id]

            if instr_name == "ret":
                instr_args = [int(b) for b in bin(instr_flags)[2:][::-1]]
                instr_args += [0] * (25 - len(instr_args))
                instr_args = [string.ascii_lowercase[i] for i, b in enumerate(instr_args) if b]

            else:
                while instr_flags:
                    arg_flag = instr_flags & 0x1f
                    instr_flags >>= 5

                    if arg_flag == 0: instr_args.append(0)
                    elif 1 <= arg_flag < 5:
                        instr_args.append(self.u(self.unpack_imm("_bhiQ"[arg_flag])))
                    else:
                        instr_args.append(string.ascii_lowercase[arg_flag - 5])

                instr_args += [0] * (5 - len(instr_args))

            if instr_name == "halt": return instr_args[0]
            self.execute_instr(instr_name, instr_args)

        raise RuntimeError("Instruction pointer outside of executable memory!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GOLF virtual machine.")
    parser.add_argument("file", help="binary to run")

    args = parser.parse_args()

    with open(args.file, "rb") as binfile:
        golf = GolfCPU(binfile.read())
        ret = golf.run()
        
        print("Execution terminated after {} cycles with exit code {}. Register file at exit:"
              .format(golf.cycle_count, ret))
        for reg in string.ascii_lowercase:
            print("{0}: {1:<20} 0x{1:x}".format(reg, golf.regs[reg]))
