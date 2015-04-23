### _GOLF_ reference assembler.

The reference assembler is written in Python3. It turns a human readable
assembly file into binary code that can run on the _GOLF_. The format is a
simple one-instruction-per-line, with commas seperating arguments. The
destinations always come before the operands. For example `a = b + c`:

    add a, b, c

The assembler supports a couple preprocessor quality-of-life enhancements over
just a series of instructions:

    # Everything after a pound (#) is a comment.
    # All operations are one-per-line, end a line in a backslash (\) followed by
    # only whitespace to split up long lines.

    # You may assign arbitrary Python expressions to an assembly variable
    # (registers are special objects).
    tmp = a

    # A label is an identifier of the form [a-zA-Z_][a-zA-Z0-9_]+ followed by a
    # colon. It is replaced in the final code by an offset in bytes from the
    # start of the instruction stream to the first instruction after the label.
    tolower:     
        # Arguments may be full Python expressions, as long as they evaluate to
        # a 64-bit integer or a register.
        in c
        add tmp, c, ord("a") - ord("A") # Equivalent to add a, c, 32.
        out tmp
        jmp tolower

Finally, you can put read-only data into the binary, and get back an address to
it by calling the `data()` function. Repeated calls to the same data will return
the same address:

    # Strings get turned into UTF-8 encoded series of bytes followed by a 0.
    hello_world = "Hello, world!" 

    # Bytes are embedded as-is,
    rawbytes = b"\x00\x01"

    # Lists of integers will become a series of 64-bit little-endian integers in
    # the data section.
    small_squares = [n*n for n in range(10)] 

        mov a, data(hello_world)
    print_loop:
        lbu c, a
        jz  c, done
        inc a
        out c
    done:
        halt

---

### _GOLF_ specification.

The CPU has 26 general-purpose registers, `a`-`z`. All registers are 64 bit
integers - there is no floating point. Signed integers are stored as two's
complement. Memory is read/written in little endian. The _GOLF_ has no pipeline
\- every instruction is executed in order, and the previous instruction must
always complete before the next one starts.

Every instruction can have output registers and input operands. Operands can be
source registers, or full 64 bit immediates. The instruction will always take a
constant amount of cycles to complete. No two instructions can run at the same
time, and all registers/memory are immediately updated after an instruction
completes.

There are no flags, exceptions, traps, or any features of that kind. The CPU
either runs its program until it halts, or until it encounters an error
(division by zero, invalid memory access) - then the CPU halts unconditionally.
A virtual machine implementation will likely produce debugging output.

The virtual machine will have a user-defined amount of heap and stack memory
available for the _GOLF_. It is also possible that the memory will grow
on-demand. The heap starts at memory address `0`, the stack starts at memory
address `0x1000000000000000`, and both grow upwards. There is no implicitly
addressed _ztack_ pointer in _GOLF_, but `z` will always be `0x1000000000000000`
at program startup, the other registers will be `0`.

Memory address `0xffffffffffffffff` is special - stores to this address will be
written to the virtual machine's stdin, reads come from stdout. You may only
use `lw` and `sw` to load/store at this address, and both only store / load the
lowest byte of the register. `lw` gives back -1 on EOF.

Instructions do not live in regular memory - they're in a seperate instruction
memory that's neither readable nor writable. This memory starts at address `0`.
Jump instructions take addresses into this memory. Execution may not go outside
of the bounds of this memory - use the `halt` instruction to stop execution.

Below is a list of all _GOLF_ instructions. Some instructions are
_pseudo-instructions_ and should be translated to real instructions by the
assembler.  For example `mov r, a` is the same as `add r, a, 0`.
_pseudo-instructions_ will be marked by an apostrophe (`'`) in the listing.

Here are all the simple register-to-register instructions:

    instruction    | cycle | mnemonic               | C syntax (uint64_t a, b) 
    ---------------+-------+------------------------+---------------------------
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

A note on the shifts - unlike in C, any value for `b` is allowed and does the
right thing on the _GOLF_.

The more complex register-to-register instructions:

    instruction     | cycle | mnemonic | description
    ----------------+-------+----------+----------------------------------------
    mul  r, s, a, b |    3  | multiply | Signed multiplication of a and b. Low
                    |       |          | 64 bits go into r, high 64 bits into s.
    mulu r, s, a, b |    3  | multiply | Unsigned multiplication of a and b. Low
                    |       |          | 64 bits go into r, high 64 bits into s.
    div  r, s, a, b |   10  | divide   | Signed division of a by b. Quotient
                    |       |          | goes in r, remainder in s.
    divu r, s, a, b |   10  | divide   | Unsigned division of a by b. Quotient
                    |       |          | goes in r, remainder in s.

Signed division and modulus work like they do in Python - the sign of the result
is the same as the sign of the divisor, and rounds towards negative infinity.

Memory and I/O instructions (`a` is a memory address for all below
instructions):

    instruction    | cycle | mnemonic            | description
    ---------------+-------+---------------------+------------------------------
    lb   r, a      |    5  | load byte           | Load and sign-extend 
                   |       |                     | 8-bit int at a.
    lbu  r, a      |    5  | load unsigned byte  | Load 8-bit int at a.
    ls   r, a      |    5  | load short          | Load and sign-extend 16-bit 
                   |       |                     | int at a.
    lsu  r, a      |    5  | load unsigned short | Load 16-bit int at a.
    li   r, a      |    5  | load int            | Load and sign-extend 32-bit 
                   |       |                     | int at a.
    lsu  r, a      |    5  | load unsigned int   | Load 32-bit int at a.
    lw   r, a      |    5  | load word           | Load 64-bit int at a.
    sb   a, b      |    1  | store byte          | Store 8-bit int b at a.
    ss   a, b      |    1  | store short         | Store 16-bit int b at a.
    si   a, b      |    1  | store int           | Store 32-bit int b at a.
    sw   a, b      |    1  | store word          | Store 64-bit int b at a.
    push a, b    ' |    2  | push                | Store 64-bit int b at a
                   |       |                     | and increment a by 8.
    pop  r, a    ' |    6  | pop                 | Decrement a by 8 and load
                   |       |                     | 64-bit int at a.
    rand r         |  100  | random              | Put random 64-bit int in r.
    
Flow control:

    instruction    | cycle | mnemonic            | description
    ---------------+-------+---------------------+------------------------------
    call f         |    1  | function call       | Saves all registers except z
                   |       |                     | and jump to f.
    ret  ...       |    1  | function return     | Restore all but the given
                   |       |                     | registers and jump to caller.
    jmp  l       ' |    1  | unconditional jump  | Unconditionally jumps to l.
    jz   l, a      |    1  | jump on zero        | Jumps to l if a is zero.
    jnz  l, a      |    1  | jump on non-zero    | Jumps to l if a is non-zero.
    halt a         |    9  | halt                | Halts the CPU with error code
                   |       |                     | a. Error code 0 is success.

---

Everything below this line is only of interest to those looking to implement a
_GOLF_ assembler, virtual machine or other tool.

### _GOLF_ instruction encoding.

Every instruction in _GOLF_ is `4 + i` bytes long, where `i` is the total size
of immediates used in that instruction. The first 7 bits of the instruction form
the instruction id.

If the instruction id is `0x7f`, the instruction is a `ret` instruction. The
remaining 25 bits each tell you whether or not that register should be restored,
with the least significant bit being `a`, and the most significant bit `y`.

Otherwise, the instruction id can be found in the table below. The next `5*5`
bits tell you what arguments for the instruction are. Each quintet of bits is to
be interpreted as following:

    0    immediate value 0
    1    8 bit signed immediate
    2    16 bit signed immediate
    3    32 bit signed immediate
    4    64 bit immediate
    5-30 register a-z

Then the non-zero immediate values - if any - come after, in the order they were
used in the instruction.

All instruction ids can be found in the table below:

    id | instr   id | instr    id | instr
    ---+------   ---+------    ---+------
    00 | not     10 | mulu     20 | jz     
    01 | or      11 | div      21 | jnz    
    02 | xor     12 | divu     22 | halt   
    03 | and     13 | lb       7f | ret    
    04 | shl     14 | lbu      
    05 | shr     15 | ls       
    06 | sar     16 | lsu      
    07 | add     17 | li       
    08 | sub     18 | liu      
    09 | cmp     19 | lw       
    0a | neq     1a | sb       
    0b | le      1b | ss       
    0c | leq     1c | si       
    0d | leu     1d | sw       
    0e | lequ    1e | rand     
    0f | mul     1f | call     
                       
### _GOLF_ binary format.

The first 4 bytes of the binary format is a little-endian 32-bit unsigned number
indicating how large the data section is. Then follows that many bytes of data
that will be accessible at starting address `0x2000000000000000`. Then the
instruction stream begins, going until the end of the file.
                       
                       
                       
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    







