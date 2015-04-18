### _GOLF_ specification.

The CPU has 26 general-purpose registers, `a`-`z`. All registers are 64 bit integers -
there is no floating point. Signed integers are stored as two's complement. Memory is
read/written in little endian. The _GOLF_ has no pipeline - every instruction is
executed in order, and the previous instruction must always complete before the next one
starts.

Every instruction can have output registers and input operands. Operands can be source
registers, or full 64 bit immediates. The instruction will always take a constant amount
of cycles to complete. No two instructions can run at the same time, and all
registers/memory are immediately updated after an instruction completes.

There are no flags, exceptions, traps, or any features of that kind. The CPU either runs
its program until it halts, or until it encounters an error (division by zero, invalid
memory access) - then the CPU halts unconditionally. A virtual machine implementation
will likely produce debugging output.

The virtual machine will have a user-defined amount of heap and stack memory available
for the _GOLF_. It is also possible that the memory will grow on-demand. The heap starts
at memory address `0`, the stack starts at memory address `0xf0000000`, and both grow
upwards. There is no implicitly addressed _ztack_ pointer in _GOLF_, but `z` will always
be `0xf0000000` at program startup.

The byte at memory address `0xffffffff` is special - stores to this address will be
written to the virtual machine's stdin, reads come from stdout.

Instructions do not live in regular memory - they're in a seperate instruction memory
that's neither readable nor writable. This memory starts at address `0`. Jump
instructions take addresses into this memory.

Now comes a list of all _GOLF_ instructions. Some instructions are
_pseudo-instructions_ and should be translated to real instructions by the assembler.
For example `mov r, a` is the same as `add r, a, 0`. _pseudo-instructions_ will be
marked by an apostrophe (`'`) in the listing.

Here are all the simple register-to-register instructions:

    instruction    | cycle | mnemonic               | similar C syntax (uint64_t a, b) 
    ---------------+-------+------------------------+---------------------------------
    mov  r, a    ' |    1  | register move          | r = a
    not  r, a      |    1  | bitwise not            | r = ~a
    or   r, a, b   |    1  | bitwise or             | r = a | b
    xor  r, a, b   |    1  | bitwise xor            | r = a ^ b
    and  r, a, b   |    1  | bitwise and            | r = a & b
    shl  r, a, b   |    1  | logical shift left     | r = a << b (int64_t b)
    shr  r, a, b   |    1  | logical shift right    | r = a >> b (int64_t b)
    sal  r, a, b ' |    1  | arithmetic shift left  | r = a << b (int64_t a, b)
    sar  r, a, b   |    1  | arithmetic shift right | r = a >> b (int64_t a, b)
    inc  r       ' |    1  | increment              | r++
    dec  r       ' |    1  | decrement              | r--
    neg  r       ' |    1  | negate                 | r = -r
    add  r, a, b   |    1  | addition               | r = a + b
    sub  r, a, b   |    1  | subtraction            | r = a - b
    cmp  r, a, b   |    1  | equality               | r = a == b
    neq  r, a, b   |    1  | inequality             | r = a != b
    le   r, a, b   |    1  | less                   | r = a < b  (int64_t a, b)
    ge   r, a, b ' |    1  | greater                | r = a > b  (int64_t a, b)
    leq  r, a, b   |    1  | less or equal          | r = a <= b (int64_t a, b)
    geq  r, a, b ' |    1  | greater or equal       | r = a >= b (int64_t a, b)
    leu  r, a, b   |    1  | less                   | r = a < b  
    geu  r, a, b ' |    1  | greater                | r = a > b  
    lequ r, a, b   |    1  | less or equal          | r = a <= b 
    gequ r, a, b ' |    1  | greater or equal       | r = a >= b 

A note on the shifts - unlike in C, any value for `b` is allowed and does the right
thing on the _GOLF_.

The more complex register-to-register instructions:

    instruction     | cycle | mnemonic       | description
    ----------------+-------+----------------+------------------------------------------
    mul  r, s, a, b |    3  | multiplication | Signed multiplication of a and b and puts
                    |       |                | the lower 64 bits of the result in r, and
                    |       |                | the higher 64 bits in s.
    mulu r, s, a, b |    3  | multiplication | Unsigned multiplication of a and b and
                    |       |                | puts the lower 64 bits of the result in
                    |       |                | r, and the higher 64 bits in s.
    div  r, s, a, b |   10  | division       | Signed division of a by b. Puts the
                    |       |                | result in r and the remainder in s.
    divu r, s, a, b |   10  | division       | Unsigned division number a by b. Puts the
                    |       |                | result in r and the remainder in s.

Memory and I/O instructions:

    instruction    | cycle | mnemonic            | description
    ---------------+-------+---------------------+------------------------------------
    lb   r, a      |    5  | load byte           | Loads and sign-extends an 8-bit int
                   |       |                     | at address a.
    lbu  r, a      |    5  | load unsigned byte  | Loads an 8-bit int at address a.
    ls   r, a      |    5  | load short          | Loads and sign-extends a 16-bit int
                   |       |                     | at address a.
    lsu  r, a      |    5  | load unsigned short | Loads a 16-bit int at address a.
    li   r, a      |    5  | load int            | Loads and sign-extends a 32-bit int
                   |       |                     | at address a.
    lsu  r, a      |    5  | load unsigned int   | Loads a 32-bit int at address a.
    lw   r, a      |    5  | load word           | Loads a 64-bit int at address a.
    sb   a, b      |    1  | store byte          | Stores an 8-bit int b at address a.
    ss   a, b      |    1  | store short         | Stores a 16-bit int b at address a.
    si   a, b      |    1  | store int           | Stores a 32-bit int b at address a.
    sw   a, b      |    1  | store word          | Stores a 64-bit int b at address a.
    push a, b    ' |    2  | push                | Stores a 64-bit int b at address a
                   |       |                     | and increments a by 8.
    pop  a, b    ' |    6  | pop                 | Reads a 64-bit int b at address a and
                   |       |                     | decrements a by 8.
    in   a       ' |    5  | stdin               | Reads one byte from stdin into a.
    out  a       ' |    1  | stdout              | Writes the low 8 bits of a to stdout.
    rand a         |   
    
Flow control:

    instruction    | cycle | mnemonic            | description
    ---------------+-------+---------------------+------------------------------
    call f         |    1  | function call       | Saves all registers and jump to f.
    ret  ...       |    1  | function return     | Restore all but the given registers.
                   |       |                     | z is never restored.
    jmp  l       ' |    1  | unconditional jump  | Unconditionally jumps to l.
    jz   l, a      |    1  | jump on zero        | Jumps to l if a is zero.
    jnz  l, a      |    1  | jump on non-zero    | Jumps to l if a is non-zero.
    halt           |    1  | halt                | Halts the CPU.

Every instruction in _GOLF_ is `4 + 8*i` bytes long, where `i` is the number of
immediates used in that instruction. `ret` is the only exception to the rules that
follow, so we'll discuss it first.

If the first 7 bits of the instruction are all 1s, the instruction is a `ret`
instruction. The remaining 25 bits each tell whether or not that register should be
restored, with the least significant bit being `a`, and the most significant bit `y`.

If the instruction is not a `ret`, then the first 7 bits of the instruction form the
instruction id, which tells you what instruction it is. The next `5*5` bits tell you
what the register arguments for the instruction are. Each quintet of bits is to be
interpreted as following:

    0    no argument
    1    immediate argument 
    2-27 register a-z

Then the 64-bit immediate values come after, in the order they were used in the
instruction.

### _GOLF_ reference assembler.

The reference assembler is written in Python3, and as such requries you to have it
installed.

The assembler supports a couple quality-of-life enhancements:

    ; comments
    labels:     ; a label must be an identifier of the form [a-zA-Z_][a-zA-Z0-9_]+


