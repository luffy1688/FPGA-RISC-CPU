`default_nettype none
package rv32i_pkg;
  localparam logic [6:0] OP_LUI=7'b0110111, OP_AUIPC=7'b0010111,
    OP_JAL=7'b1101111, OP_JALR=7'b1100111, OP_BRANCH=7'b1100011,
    OP_LOAD=7'b0000011, OP_STORE=7'b0100011, OP_OPIMM=7'b0010011,
    OP_OP=7'b0110011, OP_SYSTEM=7'b1110011, OP_CUSTOM=7'b1111011;
  // ADS does not implement SystemVerilog enum types.  Keep the same 4-bit
  // encoding as plain localparams so the package remains synthesizable.
  localparam logic [3:0] A_ADD=4'd0, A_SUB=4'd1, A_SLL=4'd2,
    A_SLT=4'd3, A_SLTU=4'd4, A_XOR=4'd5, A_SRL=4'd6,
    A_SRA=4'd7, A_OR=4'd8, A_AND=4'd9, A_MUL=4'd10;
  function automatic logic [31:0] sext12(input logic [11:0] x); sext12={{20{x[11]}},x}; endfunction
  function automatic logic [31:0] sext13(input logic [12:0] x); sext13={{19{x[12]}},x}; endfunction
  function automatic logic [31:0] sext21(input logic [20:0] x); sext21={{11{x[20]}},x}; endfunction
endpackage
`default_nettype wire
