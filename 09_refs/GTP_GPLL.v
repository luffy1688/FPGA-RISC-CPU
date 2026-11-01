//////////////////////////////////////////////////////////////////////////////
//
// Copyright (c) 2019 PANGO MICROSYSTEMS, INC
// ALL RIGHTS RESERVED.
//
// THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
// IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
// PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
//
//////////////////////////////////////////////////////////////////////////////
//
// Library: General technology primitive
// Filename: GTP_GPLL.v
//
// Functional description:
//
// Parameter description:
//
// Port description:
//
// Revision:
//
//////////////////////////////////////////////////////////////////////////////

`timescale 1ns/1fs
module GTP_GPLL #(
    parameter real CLKIN_FREQ = 50.0,    //10MHz~800MHz
    parameter LOCK_MODE       = 1'b0,    //1'b0~1'b1
    parameter integer STATIC_RATIOI = 1,   //1~128
    parameter integer STATIC_RATIOM = 1,   //1~128
    parameter real    STATIC_RATIO0 = 1.0, //1~128 or 2.000~128.000
    parameter integer STATIC_RATIO1 = 1,   //1~128
    parameter integer STATIC_RATIO2 = 1,   //1~128
    parameter integer STATIC_RATIO3 = 1,   //1~128
    parameter integer STATIC_RATIO4 = 1,   //1~128
    parameter integer STATIC_RATIO5 = 1,   //1~128
    parameter integer STATIC_RATIO6 = 1,   //1~128
    parameter real    STATIC_RATIOF = 1.0, //1~128 or 2.000~128.000
    parameter integer STATIC_DUTY0 = 2, //2<=STATIC_DUTY0<=2*STATIC_RATIO0-1
    parameter integer STATIC_DUTY1 = 2, //2<=STATIC_DUTY1<=2*STATIC_RATIO1-1
    parameter integer STATIC_DUTY2 = 2, //2<=STATIC_DUTY2<=2*STATIC_RATIO2-1
    parameter integer STATIC_DUTY3 = 2, //2<=STATIC_DUTY3<=2*STATIC_RATIO3-1
    parameter integer STATIC_DUTY4 = 2, //2<=STATIC_DUTY4<=2*STATIC_RATIO4-1
    parameter integer STATIC_DUTY5 = 2, //2<=STATIC_DUTY5<=2*STATIC_RATIO5-1
    parameter integer STATIC_DUTY6 = 2, //2<=STATIC_DUTY6<=2*STATIC_RATIO6-1
    parameter integer STATIC_DUTYF = 2, //2<=STATIC_DUTYF<=2*STATIC_RATIOF-1
    parameter integer STATIC_PHASE   = 0, //0~63
    parameter integer STATIC_PHASE0  = 0, //0~7
    parameter integer STATIC_PHASE1  = 0, //0~7
    parameter integer STATIC_PHASE2  = 0, //0~7
    parameter integer STATIC_PHASE3  = 0, //0~7
    parameter integer STATIC_PHASE4  = 0, //0~7
    parameter integer STATIC_PHASE5  = 0, //0~7
    parameter integer STATIC_PHASE6  = 0, //0~7
    parameter integer STATIC_PHASEF  = 0, //0~7
    parameter integer STATIC_CPHASE0 = 0, //0~127
    parameter integer STATIC_CPHASE1 = 0, //0~127
    parameter integer STATIC_CPHASE2 = 0, //0~127
    parameter integer STATIC_CPHASE3 = 0, //0~127
    parameter integer STATIC_CPHASE4 = 0, //0~127
    parameter integer STATIC_CPHASE5 = 0, //0~127
    parameter integer STATIC_CPHASE6 = 0, //0~127
    parameter integer STATIC_CPHASEF = 0, //0~127
    parameter CLK_DPS0_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS1_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS2_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS3_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS4_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS5_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPS6_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_DPSF_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLK_CAS5_EN  = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT0_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT1_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT2_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT3_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT4_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT5_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUT6_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter CLKOUTF_SYN_EN = "FALSE", //"TRUE"; "FALSE"
    parameter SSC_MODE      = "DISABLE",//"DOWN_LOW"; "DOWN_HIGH"; "CENTER_LOW"; "CENTER_HIGH"; "DISABLE";
    parameter real SSC_FREQ = 50.0,     //25KHz~250KHz;
    parameter INTERNAL_FB = "CLKOUTF",  //"CLKOUT0"; "CLKOUT1"; "CLKOUT2"; "CLKOUT3"; "CLKOUT4"; "CLKOUT5"; "CLKOUT6"; "CLKOUTF"; "DISABLE";
    parameter EXTERNAL_FB = "DISABLE",  //"CLKOUT0"; "CLKOUT1"; "CLKOUT2"; "CLKOUT3"; "CLKOUT4"; "CLKOUT5"; "CLKOUT6"; "CLKOUTF"; "DISABLE";
    parameter BANDWIDTH   = "OPTIMIZED" //"LOW"; "OPTIMIZED"; "HIGH"
    )(
    output CLKOUT0,
    output CLKOUT0N,
    output CLKOUT1,
    output CLKOUT1N,
    output CLKOUT2,
    output CLKOUT2N,
    output CLKOUT3,
    output CLKOUT3N,
    output CLKOUT4,
    output CLKOUT5,
    output CLKOUT6,
    output CLKOUTF,
    output CLKOUTFN,
    output LOCK,
    output DPS_DONE,
    output [15:0] APB_RDATA,
    output APB_READY,
    input CLKIN1,
    input CLKIN2,
    input CLKFB,
    input CLKIN_SEL,
    input DPS_CLK,
    input DPS_EN,
    input DPS_DIR,
    input CLKOUT0_SYN,
    input CLKOUT1_SYN,
    input CLKOUT2_SYN,
    input CLKOUT3_SYN,
    input CLKOUT4_SYN,
    input CLKOUT5_SYN,
    input CLKOUT6_SYN,
    input CLKOUTF_SYN,
    input PLL_PWD,
    input RST,
    input APB_CLK,
    input APB_RST_N,
    input [4:0] APB_ADDR,
    input APB_SEL,
    input APB_EN,
    input APB_WRITE,
    input [15:0] APB_WDATA
    );

    initial
    begin
        if((CLK_DPS0_EN == "TRUE") || (CLK_DPS0_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT0_DPS_EN");

        if((CLK_DPS1_EN == "TRUE") || (CLK_DPS1_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT1_DPS_EN");

        if((CLK_DPS2_EN == "TRUE") || (CLK_DPS2_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT2_DPS_EN");

        if((CLK_DPS3_EN == "TRUE") || (CLK_DPS3_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT3_DPS_EN");

        if((CLK_DPS4_EN == "TRUE") || (CLK_DPS4_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT4_DPS_EN");

        if((CLK_DPS5_EN == "TRUE") || (CLK_DPS5_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT5_DPS_EN");

        if((CLK_DPS6_EN == "TRUE") || (CLK_DPS6_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT6_DPS_EN");

        if((CLK_DPSF_EN == "TRUE") || (CLK_DPSF_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLK_DPSF_EN");

        if((CLK_CAS5_EN  == "TRUE") || (CLK_CAS5_EN  == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLK_CAS5_EN ");

        if((CLKOUT0_SYN_EN == "TRUE") || (CLKOUT0_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT0_SYN_EN");

        if((CLKOUT1_SYN_EN == "TRUE") || (CLKOUT1_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT1_SYN_EN");

        if((CLKOUT2_SYN_EN == "TRUE") || (CLKOUT2_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT2_SYN_EN");

        if((CLKOUT3_SYN_EN == "TRUE") || (CLKOUT3_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT3_SYN_EN");

        if((CLKOUT4_SYN_EN == "TRUE") || (CLKOUT4_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT4_SYN_EN");

        if((CLKOUT5_SYN_EN == "TRUE") || (CLKOUT5_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT5_SYN_EN");

        if((CLKOUT6_SYN_EN == "TRUE") || (CLKOUT6_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUT6_SYN_EN");

        if((CLKOUTF_SYN_EN == "TRUE") || (CLKOUTF_SYN_EN == "FALSE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for CLKOUTF_SYN_EN");

        if((INTERNAL_FB == "CLKOUT0") || (INTERNAL_FB == "CLKOUT1") || (INTERNAL_FB == "CLKOUT2") || (INTERNAL_FB == "CLKOUT3") || (INTERNAL_FB == "CLKOUT4") || (INTERNAL_FB == "CLKOUT5") || (INTERNAL_FB == "CLKOUT6") || (INTERNAL_FB == "CLKOUTF") || (INTERNAL_FB == "DISABLE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for INTERNAL_FB");

        if((EXTERNAL_FB == "CLKOUT0") || (EXTERNAL_FB == "CLKOUT1") || (EXTERNAL_FB == "CLKOUT2") || (EXTERNAL_FB == "CLKOUT3") || (EXTERNAL_FB == "CLKOUT4") || (EXTERNAL_FB == "CLKOUT5") || (INTERNAL_FB == "CLKOUT6") || (EXTERNAL_FB == "CLKOUTF") || (EXTERNAL_FB == "DISABLE"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for EXTERNAL_FB");

        if((BANDWIDTH == "LOW") || (BANDWIDTH == "OPTIMIZED") || (BANDWIDTH == "HIGH"))
        begin
        end
        else
            $display ("GTP_GPLL error: illegal setting for BANDWIDTH");
    end
///////////////////////////////////////////////////////
////INITIAL////////////////////////////////////////////
    reg [7:0] ratioi_i, ratiom_i, ratiof_i, ratio0_i, ratio1_i, ratio2_i, ratio3_i, ratio4_i, ratio5_i, ratio6_i;
    reg [7:0] dutyf_i, duty0_i, duty1_i, duty2_i, duty3_i, duty4_i, duty5_i, duty6_i;
    reg [6:0] odiv0_cphase_i, odiv1_cphase_i, odiv2_cphase_i, odiv3_cphase_i, odiv4_cphase_i, odiv5_cphase_i, odiv6_cphase_i, fdiv_cphase_i;
    reg [2:0] odiv0_fphase_i, odiv1_fphase_i, odiv2_fphase_i, odiv3_fphase_i, odiv4_fphase_i, odiv5_fphase_i, odiv6_fphase_i, fdiv_fphase_i;

    reg [2:0] ratio0_frac_i, ratiof_frac_i;
    reg [2:0] psoffset0_i, psoffsetf_i;

    reg muxsel0_en_i, muxsel1_en_i, muxsel2_en_i, muxsel3_en_i, muxsel4_en_i, muxsel5_en_i, muxsel6_en_i, muxself_en_i;
    reg [1:0] muxsel0_i, muxsel1_i, muxsel2_i, muxsel3_i, muxsel4_i, muxsel5_i, muxsel6_i, muxself_i;

    reg odiv0_frac_en_i, fdiv_frac_en_i;
    reg [1:0] odiv0_frac_adjust_i, fdiv_frac_adjust_i;

    reg [15:0] mem0, mem1, mem2, mem3, mem4, mem5, mem6, mem7, mem8, mem9, mem10, mem11, mem12, mem13, mem14, mem15, mem16, mem17, mem18, mem19, mem20, mem21;
    reg [1:0] vctrl_i;
    reg [1:0] cp_selbias_i, cp_base_i;
    reg [3:0] cp_cur_i;
    reg [2:0] lpf_r_i;
    reg lpf_c_i;
    reg [5:0] lock_set_i;
    reg lockfilter_pd_i;

    integer dps_init;
    reg odiv0_dps_en, odiv1_dps_en, odiv2_dps_en, odiv3_dps_en, odiv4_dps_en, odiv5_dps_en, odiv6_dps_en, fdiv_dps_en;
    reg div_dps_en;

    integer ratio0_int, ratiof_int;
    real ratio0_fra, ratiof_fra;

    wire [7:0] ratioi, ratiom, ratiof, ratio0, ratio1, ratio2, ratio3, ratio4, ratio5, ratio6;
    wire [7:0] dutyf, duty0, duty1, duty2, duty3, duty4, duty5, duty6;
    wire [6:0] odiv0_cphase, odiv1_cphase, odiv2_cphase, odiv3_cphase, odiv4_cphase, odiv5_cphase, odiv6_cphase, fdiv_cphase;
    wire [2:0] odiv0_fphase, odiv1_fphase, odiv2_fphase, odiv3_fphase, odiv4_fphase, odiv5_fphase, odiv6_fphase, fdiv_fphase;
    
    wire [2:0] ratio0_frac, ratiof_frac;
    wire [2:0] psoffset0, psoffsetf;

    wire muxsel0_en, muxsel1_en, muxsel2_en, muxsel3_en, muxsel4_en, muxsel5_en, muxsel6_en, muxself_en;
    wire [1:0] muxsel0, muxsel1, muxsel2, muxsel3, muxsel4, muxsel5, muxsel6, muxself;

    wire odiv0_frac_en, fdiv_frac_en;
    wire [1:0] odiv0_frac_adjust, fdiv_frac_adjust;

    initial
    begin
        ratioi_i = STATIC_RATIOI;
        ratiom_i = STATIC_RATIOM;
        ratiof_i = $rtoi(STATIC_RATIOF);
        ratio0_i = $rtoi(STATIC_RATIO0);
        ratio1_i = STATIC_RATIO1;
        ratio2_i = STATIC_RATIO2;
        ratio3_i = STATIC_RATIO3;
        ratio4_i = STATIC_RATIO4;
        ratio5_i = STATIC_RATIO5;
        ratio6_i = STATIC_RATIO6;
        dutyf_i = STATIC_DUTYF;
        duty0_i = STATIC_DUTY0;
        duty1_i = STATIC_DUTY1;
        duty2_i = STATIC_DUTY2;
        duty3_i = STATIC_DUTY3;
        duty4_i = STATIC_DUTY4;
        duty5_i = STATIC_DUTY5;
        duty6_i = STATIC_DUTY6;
        odiv0_cphase_i = STATIC_CPHASE0;
        odiv1_cphase_i = STATIC_CPHASE1;
        odiv2_cphase_i = STATIC_CPHASE2;
        odiv3_cphase_i = STATIC_CPHASE3;
        odiv4_cphase_i = STATIC_CPHASE4;
        odiv5_cphase_i = STATIC_CPHASE5;
        odiv6_cphase_i = STATIC_CPHASE6;
        fdiv_cphase_i  = STATIC_CPHASEF;
        odiv0_fphase_i = STATIC_PHASE0;
        odiv1_fphase_i = STATIC_PHASE1;
        odiv2_fphase_i = STATIC_PHASE2;
        odiv3_fphase_i = STATIC_PHASE3;
        odiv4_fphase_i = STATIC_PHASE4;
        odiv5_fphase_i = STATIC_PHASE5;
        odiv6_fphase_i = STATIC_PHASE6;
        fdiv_fphase_i  = STATIC_PHASEF;
        muxsel0_en_i = 1'b1;
        muxsel1_en_i = 1'b1;
        muxsel2_en_i = 1'b1;
        muxsel3_en_i = 1'b1;
        muxsel4_en_i = 1'b1;
        muxsel5_en_i = 1'b1;
        muxsel6_en_i = 1'b1;
        muxself_en_i = 1'b1;
        vctrl_i        = 2'b00;
        cp_selbias_i   = 2'b01;
        cp_base_i      = 2'b10;
        cp_cur_i       = 4'b0001;
        lpf_r_i        = 3'b001;
        lpf_c_i        = 1'b0;
        lock_set_i      = 5'h0;
        lockfilter_pd_i = 1'b1;

        dps_init = STATIC_PHASE;

        if(CLK_DPS0_EN == "TRUE")
        begin
            muxsel0_i    = 2'b01;
            odiv0_dps_en = 1'b1;
        end
        else
        begin
            muxsel0_i    = 2'b00;
            odiv0_dps_en = 1'b0;
        end

        if(CLK_DPS1_EN == "TRUE")
        begin
            muxsel1_i    = 2'b01;
            odiv1_dps_en = 1'b1;
        end
        else
        begin
            muxsel1_i    = 2'b00;
            odiv1_dps_en = 1'b0;
        end

        if(CLK_DPS2_EN == "TRUE")
        begin
            muxsel2_i    = 2'b01;
            odiv2_dps_en = 1'b1;
        end
        else
        begin
            muxsel2_i    = 2'b00;
            odiv2_dps_en = 1'b0;
        end

        if(CLK_DPS3_EN == "TRUE")
        begin
            muxsel3_i    = 2'b01;
            odiv3_dps_en = 1'b1;
        end
        else
        begin
            muxsel3_i    = 2'b00;
            odiv3_dps_en = 1'b0;
        end

        if(CLK_DPS4_EN == "TRUE")
        begin
            muxsel4_i    = 2'b01;
            odiv4_dps_en = 1'b1;
        end
        else
        begin
            muxsel4_i    = 2'b00;
            odiv4_dps_en = 1'b0;
        end

        if(CLK_DPS5_EN == "TRUE")
        begin
            muxsel5_i    = 2'b01;
            odiv5_dps_en = 1'b1;
        end
        else if(CLK_CAS5_EN == "TRUE")
        begin
            muxsel5_i    = 2'b10;
            odiv5_dps_en = 1'b0;
        end
        else
        begin
            muxsel5_i    = 2'b00;
            odiv5_dps_en = 1'b0;
        end

        if(CLK_DPS6_EN == "TRUE")
        begin
            muxsel6_i    = 2'b01;
            odiv6_dps_en = 1'b1;
        end
        else
        begin
            muxsel6_i    = 2'b00;
            odiv6_dps_en = 1'b0;
        end

        if(CLK_DPSF_EN == "TRUE")
        begin
            muxself_i   = 2'b01;
            fdiv_dps_en = 1'b1;
        end
        else
        begin
            muxself_i   = 2'b00;
            fdiv_dps_en = 1'b0;
        end

        div_dps_en = odiv0_dps_en || odiv1_dps_en || odiv2_dps_en || odiv3_dps_en || odiv4_dps_en || odiv5_dps_en || odiv6_dps_en || fdiv_dps_en;

        ratio0_int    = $rtoi(STATIC_RATIO0);
        ratio0_fra    = STATIC_RATIO0 - ratio0_int;
        ratio0_frac_i = ratio0_fra * 8;
        
        if(ratio0_fra > 0.000)
        begin
            odiv0_frac_en_i = 1'b1;
            if(!ratio0_i[0])
            begin
                psoffset0_i = (ratio0_frac_i + 1'b1) / 2 + odiv0_fphase_i;
                if(ratio0_fra > 0.000 && ratio0_fra < 0.875)
                    odiv0_frac_adjust_i = 2'b11;
                else
                    odiv0_frac_adjust_i = 2'b10;
            end
            else
            begin
                psoffset0_i = ({1'b0, ratio0_frac_i} + 4'd9) / 2 + odiv0_fphase_i;
                if(ratio0_fra > 0.000 && ratio0_fra < 0.875)
                    odiv0_frac_adjust_i = 2'b00;
                else
                    odiv0_frac_adjust_i = 2'b01;
            end
        end
        else
        begin
            odiv0_frac_en_i     = 1'b0;
            psoffset0_i         = 3'b000;
            odiv0_frac_adjust_i = 2'b00;
        end

        ratiof_int    = $rtoi(STATIC_RATIOF);
        ratiof_fra    = STATIC_RATIOF - ratiof_int;
        ratiof_frac_i = ratiof_fra * 8;
        
        if(ratiof_fra > 0.000)
        begin
            fdiv_frac_en_i = 1'b1;
            if(!ratiof_i[0])
            begin
                psoffsetf_i = (ratiof_frac_i + 1'b1) / 2 + fdiv_fphase_i;
                if(ratiof_fra > 0.000 && ratiof_fra < 0.875)
                    fdiv_frac_adjust_i = 2'b11;
                else
                    fdiv_frac_adjust_i = 2'b10;
            end
            else
            begin
                psoffsetf_i = ({1'b0, ratiof_frac_i} + 4'd9) / 2 + fdiv_fphase_i;
                if(ratiof_fra > 0.000 && ratiof_fra < 0.875)
                    fdiv_frac_adjust_i = 2'b00;
                else
                    fdiv_frac_adjust_i = 2'b01;
            end
        end
        else
        begin
            fdiv_frac_en_i     = 1'b0;
            psoffsetf_i        = 3'b000;
            fdiv_frac_adjust_i = 2'b00;
        end

        mem0  = {ratio0_i, duty0_i};
        mem1  = {ratio0_frac_i, psoffset0_i, odiv0_fphase_i, odiv0_cphase_i};
        mem2  = {10'h0, odiv0_frac_adjust_i, odiv0_frac_en_i, muxsel0_i, muxsel0_en_i};
        mem3  = {ratio1_i, duty1_i};
        mem4  = {3'h0, muxsel1_i, muxsel1_en_i, odiv1_fphase_i, odiv1_cphase_i};
        mem5  = {ratio2_i, duty2_i};
        mem6  = {3'h0, muxsel2_i, muxsel2_en_i, odiv2_fphase_i, odiv2_cphase_i};
        mem7  = {ratio3_i, duty3_i};
        mem8  = {3'h0, muxsel3_i, muxsel3_en_i, odiv3_fphase_i, odiv3_cphase_i};
        mem9  = {ratio4_i, duty4_i};
        mem10 = {3'h0, muxsel4_i, muxsel4_en_i, odiv4_fphase_i, odiv4_cphase_i};
        mem11 = {ratio5_i, duty5_i};
        mem12 = {3'h0, muxsel5_i, muxsel5_en_i, odiv5_fphase_i, odiv5_cphase_i};
        mem13 = {ratio6_i, duty6_i};
        mem14 = {3'h0, muxsel6_i, muxsel6_en_i, odiv6_fphase_i, odiv6_cphase_i};
        mem15 = {ratiof_i, dutyf_i};
        mem16 = {ratiof_frac_i, psoffsetf_i, fdiv_fphase_i, fdiv_cphase_i};
        mem17 = {10'h0, fdiv_frac_adjust_i, fdiv_frac_en_i, muxself_i, muxself_en_i};
        mem18 = {8'h0, ratioi_i};
        mem19 = {8'h0, ratiom_i};
        mem20 = {2'b00, vctrl_i, cp_selbias_i, cp_selbias_i, cp_base_i, cp_cur_i, lpf_r_i, lpf_c_i};
        mem21 = {10'h0, lockfilter_pd_i, lock_set_i};
    end

    assign ratioi = mem18[7:0];
    assign ratiom = mem19[7:0];
    assign ratiof = mem15[15:8];
    assign ratio0 = mem0[15:8];
    assign ratio1 = mem3[15:8];
    assign ratio2 = mem5[15:8];
    assign ratio3 = mem7[15:8];
    assign ratio4 = mem9[15:8];
    assign ratio5 = mem11[15:8];
    assign ratio6 = mem13[15:8];
    assign dutyf  = mem15[7:0];
    assign duty0  = mem0[7:0];
    assign duty1  = mem3[7:0];
    assign duty2  = mem5[7:0];
    assign duty3  = mem7[7:0];
    assign duty4  = mem9[7:0];
    assign duty5  = mem11[7:0];
    assign duty6  = mem13[7:0];
    assign odiv0_cphase = mem1[6:0];
    assign odiv1_cphase = mem4[6:0];
    assign odiv2_cphase = mem6[6:0];
    assign odiv3_cphase = mem8[6:0];
    assign odiv4_cphase = mem10[6:0];
    assign odiv5_cphase = mem12[6:0];
    assign odiv6_cphase = mem14[6:0];
    assign fdiv_cphase  = mem16[6:0];
    assign odiv0_fphase = mem1[9:7];
    assign odiv1_fphase = mem4[9:7];
    assign odiv2_fphase = mem6[9:7];
    assign odiv3_fphase = mem8[9:7];
    assign odiv4_fphase = mem10[9:7];
    assign odiv5_fphase = mem12[9:7];
    assign odiv6_fphase = mem14[9:7];
    assign fdiv_fphase  = mem16[9:7];
    assign ratio0_frac  = mem1[15:13];
    assign ratiof_frac  = mem16[15:13];
    assign psoffset0    = mem1[12:10];
    assign psoffsetf    = mem16[12:10];
    assign muxsel0_en = mem2[0];
    assign muxsel1_en = mem4[10];
    assign muxsel2_en = mem6[10];
    assign muxsel3_en = mem8[10];
    assign muxsel4_en = mem10[10];
    assign muxsel5_en = mem12[10];
    assign muxsel6_en = mem14[10];
    assign muxself_en = mem17[0];
    assign muxsel0    = mem2[2:1];
    assign muxsel1    = mem4[12:11];
    assign muxsel2    = mem6[12:11];
    assign muxsel3    = mem8[12:11];
    assign muxsel4    = mem10[12:11];
    assign muxsel5    = mem12[12:11];
    assign muxsel6    = mem14[12:11];
    assign muxself    = mem17[2:1];
    assign odiv0_frac_en     = mem2[3];
    assign fdiv_frac_en      = mem17[3];
    assign odiv0_frac_adjust = mem2[5:4];
    assign fdiv_frac_adjust  = mem17[5:4];
///////////////////////////////////////////////////////
    wire rst_n;
    reg inner_rstn;
///////////////////////////////////////////////////////
    wire clk_in;
///////////////////////////////////////////////////////
    reg clk_in_first_time, clk_fb_first_time;
    realtime clk_in_first_edge, clk_fb_first_edge;

    real clkin_cj;

    reg adjust;
    realtime fb_route_delay, virtual_delay1;
    integer tmp_ratio;
    realtime tmp_delay, real_delay;
///////////////////////////////////////////////////////
    reg clk_test;
    reg clkref_wo, clkfb_wo;
    realtime clkref_test_time1 , clkref_test_time2, clkref_test_time3;
    realtime clkfb_rtime_last, clkfb_rtime_next;
    realtime clkfb_test_time1 , clkfb_test_time2, clkfb_test_time3;
    wire clkwo;
///////////////////////////////////////////////////////
    wire [7:0] idivider, mdivider, fdivider, divider0, divider1, divider2, divider3, divider4, divider5, divider6;
    real fsdiv_set_int, fbdiv_set_int;

    wire rstanalog_n;
    realtime clkin_rtime_last, clkin_rtime_next;
    realtime clkin_time, clkin_time1, clkin_time2, clkin_time3;
    reg clkout_lock;
    realtime vcoclk_period, vcoclk_period_half;
    realtime clkout0_time, clkout1_time, clkout2_time, clkout3_time, clkout4_time, clkout5_time, clkout6_time, clkoutf_time;
    integer  vcoclk_period_amp;
    realtime vcoclk_period_real, vcoclk_period_dev;

    reg done;
    integer idiv_set;
    integer fdiv_set;
    integer swap_set;
    integer midd_set;
    integer fdiv_int;
    realtime offset;

    real cnt_fdiv;
    reg clk_gate, inner_clk;
    reg vcoclk;

    real new_delay;
    wire adjust_dly, frac_restart;
///////////////////////////////////////////////////////
    wire clk_lock;
    reg [2:0] cnt_clkfb;
    reg start_clk;
    reg [10:0] cnt_lock;
    reg lock_wait;
    reg lock_reg;
///////////////////////////////////////////////////////
    reg [5:0] dps_cnt;
    reg dps_cnt_finish;
    reg dps_done_reg;
    integer dps_done_cnt;
    wire [63:0] vcoclk_dps_dly;
    reg vcoclk_dps_adjust;
    integer dps_cnt_dly0, dps_cnt_dly1;
    wire vcoclk_dps;
///////////////////////////////////////////////////////
    reg odiv0_clkin, odiv1_clkin, odiv2_clkin, odiv3_clkin, odiv4_clkin, odiv5_clkin, odiv6_clkin, fdiv_clkin;
    reg [7:0] odiv0_counter, odiv1_counter, odiv2_counter, odiv3_counter, odiv4_counter, odiv5_counter, odiv6_counter, fdiv_counter;
    reg odiv0_out_reg, odiv1_out_reg, odiv2_out_reg, odiv3_out_reg, odiv4_out_reg, odiv5_out_reg, odiv6_out_reg, fdiv_out_reg;
    wire odiv0_out, odiv1_out, odiv2_out, odiv3_out, odiv4_out, odiv5_out, odiv6_out, fdiv_out;

    wire odiv0_int_out, fdiv_int_out;
    wire [2:0] divider0_frac, fdivider_frac;
    integer odiv0_p_int, odiv0_hp_frac, odiv0_lp_frac, fdiv_p_int, fdiv_hp_frac, fdiv_lp_frac;
    real odiv0_frac_hp, odiv0_frac_lp, fdiv_frac_hp, fdiv_frac_lp;
    integer i,j;
    reg odiv0_frac_out, fdiv_frac_out;
///////////////////////////////////////////////////////
    realtime vco_fphase_delay0, vco_fphase_delay1, vco_fphase_delay2, vco_fphase_delay3, vco_fphase_delay4, vco_fphase_delay5, vco_fphase_delay6, vco_fphase_delayf;
    integer cphase0, cphase1, cphase2, cphase3, cphase4, cphase5, cphase6, cphasef;
    realtime cphase_delay0, cphase_delay1, cphase_delay2, cphase_delay3, cphase_delay4, cphase_delay5, cphase_delay6, cphase_delayf;
    reg odiv0_out_delay1, odiv1_out_delay1, odiv2_out_delay1, odiv3_out_delay1, odiv4_out_delay1, odiv5_out_delay1, odiv6_out_delay1, fdiv_out_delay1;
    reg odiv0_out_delay, odiv1_out_delay, odiv2_out_delay, odiv3_out_delay, odiv4_out_delay, odiv5_out_delay, odiv6_out_delay, fdiv_out_delay;
///////////////////////////////////////////////////////
    reg [2:0] clk_out0_gate, clk_out1_gate, clk_out2_gate, clk_out3_gate, clk_out4_gate, clk_out5_gate, clk_out6_gate, clk_outf_gate;
    wire clkout0_gate, clkout1_gate, clkout2_gate, clkout3_gate, clkout4_gate, clkout5_gate, clkout6_gate, clkoutf_gate;
///////////////////////////////////////////////////////
    reg [1:0] apb_rstn_sync;
    reg ready;
    reg [15:0] rdata;
///////////////////////////////////////////////////////
    initial
    begin
        inner_rstn = 1'b0;
        clk_in_first_time = 1'b0;
        clk_fb_first_time = 1'b0;
        clk_in_first_edge = 0.0;
        clk_fb_first_edge = 0.0;
        fb_route_delay = 0.0;
        tmp_ratio      = 0;
        tmp_delay      = 0.0;
        real_delay     = 0.0;
        clk_test = 1'b0;
        fsdiv_set_int = 0;
        fbdiv_set_int = 0;
        done = 1'b0;
        idiv_set = 0;
        fdiv_set = 0;
        swap_set = 0;
        midd_set = 0;
        fdiv_int = 0;
        offset = 0;
        cnt_fdiv  = 0;
        clk_gate  = 1'b1;
        inner_clk = 1'b0;
        vcoclk    = 1'b0;
        i = 1;
        j = 1;
        vco_fphase_delay0 = 0.0;
        vco_fphase_delay1 = 0.0;
        vco_fphase_delay2 = 0.0;
        vco_fphase_delay3 = 0.0;
        vco_fphase_delay4 = 0.0;
        vco_fphase_delay5 = 0.0;
        vco_fphase_delay6 = 0.0;
        vco_fphase_delayf = 0.0;
        cphase_delay0 = 0.0;
        cphase_delay1 = 0.0;
        cphase_delay2 = 0.0;
        cphase_delay3 = 0.0;
        cphase_delay4 = 0.0;
        cphase_delay5 = 0.0;
        cphase_delay6 = 0.0;
        cphase_delayf = 0.0;
        odiv0_out_delay1 = 1'b0;
        odiv1_out_delay1 = 1'b0;
        odiv2_out_delay1 = 1'b0;
        odiv3_out_delay1 = 1'b0;
        odiv4_out_delay1 = 1'b0;
        odiv5_out_delay1 = 1'b0;
        odiv6_out_delay1 = 1'b0;
        fdiv_out_delay1  = 1'b0;
        odiv0_out_delay  = 1'b0;
        odiv1_out_delay  = 1'b0;
        odiv2_out_delay  = 1'b0;
        odiv3_out_delay  = 1'b0;
        odiv4_out_delay  = 1'b0;
        odiv5_out_delay  = 1'b0;
        odiv6_out_delay  = 1'b0;
        fdiv_out_delay   = 1'b0;
        clk_out0_gate = 3'b000;
        clk_out1_gate = 3'b000;
        clk_out2_gate = 3'b000;
        clk_out3_gate = 3'b000;
        clk_out4_gate = 3'b000;
        clk_out5_gate = 3'b000;
        clk_out6_gate = 3'b000;
        clk_outf_gate = 3'b000;
        #1;
        inner_rstn = 1'b1;
        clk_in_first_time = 1'b1;
        clk_fb_first_time = 1'b1;
    end
///////////////////////////////////////////////////////
////RESET//////////////////////////////////////////////
    assign rst_n = ~(PLL_PWD | RST) & inner_rstn;
///////////////////////////////////////////////////////
////INPUT_CLK_SEL//////////////////////////////////////
    assign clk_in = (CLKIN_SEL == 1'b0) ? CLKIN1 : CLKIN2;
///////////////////////////////////////////////////////
////FBCK_DELAY/////////////////////////////////////////
    always @(posedge clk_in or negedge rst_n)
    begin
        if(!rst_n)
        begin
            clk_in_first_time = 1'b1;
            clk_in_first_edge = 0.0;
        end
        else
        begin
            if(clk_in_first_time == 1'b1)
                clk_in_first_edge = $realtime;
            clk_in_first_time = 1'b0;
        end
    end

    always @(posedge CLKFB or negedge rst_n)
    begin
        if(!rst_n)
        begin
            clk_fb_first_time = 1'b1;
            clk_fb_first_edge = 0.0;
        end
        else
        begin
            if(clk_fb_first_time == 1'b1)
                clk_fb_first_edge = $realtime;
            clk_fb_first_time = 1'b0;
        end
    end
///////////////////////////////////////////////////////
///////////////////////////////////////////////////////
    always @(*)
    begin
        if(BANDWIDTH == "LOW" || BANDWIDTH == "OPTIMIZED")
            if(CLKIN_FREQ/idivider <= 200)
                clkin_cj = 0.45/idivider;
            else
                clkin_cj = 0.09*1000/(idivider*CLKIN_FREQ);
        else if(BANDWIDTH == "HIGH")
            if(CLKIN_FREQ/idivider <= 200)
                clkin_cj = 0.45/idivider;
            else
                clkin_cj = 0.09*1000/(idivider*CLKIN_FREQ);
    end
///////////////////////////////////////////////////////
////CLK_TEST///////////////////////////////////////////
    always #200 clk_test = ~clk_test;

    always @(posedge clk_test or negedge rst_n)
    begin
        if(!rst_n)
        begin
            clkref_wo <= 1'b0;
            clkref_test_time1 = 0;
            clkref_test_time2 = 0;
            clkref_test_time3 = 0;
        end
        else
        begin
            clkref_test_time3 = clkref_test_time2;
            clkref_test_time2 = clkref_test_time1;
            clkref_test_time1 = clkin_rtime_next;
            if(clkref_test_time3 == clkref_test_time1)
                clkref_wo <= 1'b1;
            else
                clkref_wo <= 1'b0;
        end
    end

    always @(posedge CLKFB or negedge rst_n)
    begin
        if(!rst_n)
        begin
            clkfb_rtime_last = 0.0;
            clkfb_rtime_next = 0.0;
        end
        else
        begin
            clkfb_rtime_last = clkin_rtime_next;
            clkfb_rtime_next = $realtime;
        end
    end

    always @(posedge clk_test or negedge rst_n)
    begin
        if(!rst_n)
        begin
            clkfb_wo <= 1'b0;
            clkfb_test_time3 = 0;
            clkfb_test_time2 = 0;
            clkfb_test_time1 = 0;
        end
        else
        begin
            if(clk_fb_first_time == 1'b0)
            begin
                clkfb_test_time3 = clkfb_test_time2;
                clkfb_test_time2 = clkfb_test_time1;
                clkfb_test_time1 = clkfb_rtime_next;
                if(clkfb_test_time3 == clkfb_test_time1)
                    clkfb_wo <= 1'b1;
                else
                    clkfb_wo <= 1'b0;
            end
        end
    end

    assign clkwo = clkref_wo | clkfb_wo;
///////////////////////////////////////////////////////
////PLL_ANALOG/////////////////////////////////////////
////FEEDBACK_DIVIDER_CAL///////////////////////////////
    assign idivider = ratioi;
    assign mdivider = ratiom;
    assign fdivider = ratiof;
    assign divider0 = ratio0;
    assign divider1 = ratio1;
    assign divider2 = ratio2;
    assign divider3 = ratio3;
    assign divider4 = ratio4;
    assign divider5 = ratio5;
    assign divider6 = ratio6;

    always @(*)
    begin
    	if((INTERNAL_FB == "CLKOUTF" || EXTERNAL_FB == "CLKOUTF") && fdiv_frac_en == 1'b0)
            fsdiv_set_int = fdivider;
    	else if((INTERNAL_FB == "CLKOUTF" || EXTERNAL_FB == "CLKOUTF") && fdiv_frac_en == 1'b1)
            fsdiv_set_int = fdivider + ratiof_frac * 0.125;
        else if((INTERNAL_FB == "CLKOUT0" || EXTERNAL_FB == "CLKOUT0") && odiv0_frac_en == 1'b0)
            fsdiv_set_int = divider0;
        else if((INTERNAL_FB == "CLKOUT0" || EXTERNAL_FB == "CLKOUT0") && odiv0_frac_en == 1'b1)
            fsdiv_set_int = divider0 + ratio0_frac * 0.125;
        else if(INTERNAL_FB == "CLKOUT1" || EXTERNAL_FB == "CLKOUT1")
            fsdiv_set_int = divider1;
        else if(INTERNAL_FB == "CLKOUT2" || EXTERNAL_FB == "CLKOUT2")
            fsdiv_set_int = divider2;
        else if(INTERNAL_FB == "CLKOUT3" || EXTERNAL_FB == "CLKOUT3")
            fsdiv_set_int = divider3;
        else if(INTERNAL_FB == "CLKOUT4" || EXTERNAL_FB == "CLKOUT4")
            fsdiv_set_int = divider4;
        else if(INTERNAL_FB == "CLKOUT5" || EXTERNAL_FB == "CLKOUT5")
            fsdiv_set_int = divider5;
        else if(INTERNAL_FB == "CLKOUT6" || EXTERNAL_FB == "CLKOUT6")
            fsdiv_set_int = divider6;
    end

    always @(*)
    begin
        fbdiv_set_int = mdivider * fsdiv_set_int;
    end
////PLL_VCO_CAL////////////////////////////////////////
    assign rstanalog_n = rst_n;

    always @(posedge clk_in or negedge rstanalog_n)
    begin
        if(!rstanalog_n)
        begin
            clkin_rtime_last = 0.0;
            clkin_rtime_next = 0.0;
            clkin_time  <= 0.0;
            clkin_time1 <= 0.0;
            clkin_time2 <= 0.0;
            clkin_time3 <= 0.0;
            clkout_lock <= 0.0;
            vcoclk_period <= 1'b0;
            vcoclk_period_half <= 0.0;
            clkout0_time       <= 0.0;
            clkout1_time       <= 0.0;
            clkout2_time       <= 0.0;
            clkout3_time       <= 0.0;
            clkout4_time       <= 0.0;
            vcoclk_period_amp  <= 0.0;
            vcoclk_period_real <= 0.0;
            vcoclk_period_dev  <= 0.0;
        end
        else
        begin
            clkin_rtime_last = clkin_rtime_next;
            clkin_rtime_next = $realtime;
            if(clkin_rtime_last > 0)
            begin
                clkin_time  <= clkin_rtime_next-clkin_rtime_last;
                clkin_time1 <= clkin_time;
                clkin_time2 <= clkin_time1;
                clkin_time3 <= clkin_time2;
            end
            if(clkin_time > 0)
            begin
                clkout_lock <= (clkin_time  > 0) &&
                               (clkin_time1 > 0) &&
                               (clkin_time2 > 0) &&
                               (clkin_time3 > 0) &&
                               ((clkin_time - clkin_time1)  < clkin_cj) &&
                               ((clkin_time1 - clkin_time)  < clkin_cj) &&
                               ((clkin_time1 - clkin_time2) < clkin_cj) &&
                               ((clkin_time2 - clkin_time1) < clkin_cj) &&
                               ((clkin_time2 - clkin_time3) < clkin_cj) &&
                               ((clkin_time3 - clkin_time2) < clkin_cj);
            end
            if(clkin_time > 0)
            begin
                vcoclk_period      = (clkin_time * idivider) / fbdiv_set_int;
                vcoclk_period_half = vcoclk_period / 2;
                clkout0_time       = vcoclk_period * divider0;
                clkout1_time       = vcoclk_period * divider1;
                clkout2_time       = vcoclk_period * divider2;
                clkout3_time       = vcoclk_period * divider3;
                clkout4_time       = vcoclk_period * divider4;
                clkout5_time       = vcoclk_period * divider5;
                clkout6_time       = vcoclk_period * divider6;
                clkoutf_time       = vcoclk_period * fdivider;
                vcoclk_period_amp  = vcoclk_period_half * 1000000;
                vcoclk_period_real = vcoclk_period_amp / 1000000.0;
                vcoclk_period_dev  = (clkin_time - (vcoclk_period_real * 2 * fbdiv_set_int) / idivider) / 2;
            end
        end
    end

    always @(*)
    begin
        if(!rst_n)
        begin
            done = 1'b0;
            idiv_set = 0;
            fdiv_set = 0;
            swap_set = 0;
            midd_set = 0;
            offset = 0;
        end
        else
        begin
            idiv_set = idivider;
            fdiv_set = $rtoi(fbdiv_set_int);
            while(!done)
            begin
                if(idiv_set < fdiv_set)
                begin
                    swap_set = idiv_set;
                    idiv_set = fdiv_set;
                    fdiv_set = swap_set;
                end
                else
                    if(fdiv_set != 0)
                        idiv_set = idiv_set - fdiv_set;
                    else
                    begin
                        done = 1;
                        midd_set = idiv_set;
                    end
            end
        end
    end

    always @(*)
    begin
        if(!rst_n)
        begin
            fdiv_int = 0;
            offset = 0;
        end
        else
            begin
                fdiv_int = midd_set;
                offset = vcoclk_period_dev * idivider/midd_set;
            end
    end

    always @(clkout_lock or inner_clk or clkwo)
    begin
        if(clkout_lock == 1'b0 || clkwo == 1'b1)
        begin
            inner_clk <= 1'b0;
            clk_gate  <= 1'b1;
            cnt_fdiv   = 0;
        end
        else
            if(clk_gate == 1)
            begin
                inner_clk <= 1'b1;
                clk_gate  <= 1'b0;
                cnt_fdiv   = 0;
            end
            else
            begin
                cnt_fdiv = cnt_fdiv + 1;
                if(cnt_fdiv == $rtoi(fbdiv_set_int)/fdiv_int)
                begin
                    inner_clk <= #(vcoclk_period_half + offset) ~inner_clk;
                    cnt_fdiv = 0;
                end
                else
                    inner_clk <= #vcoclk_period_half ~inner_clk;
            end
    end

    always @(posedge clk_in or CLKFB or negedge rst_n)
    begin
        if(!rst_n)
        begin
            adjust <= 1'b1;
            fb_route_delay = 0.0;
            tmp_ratio  = 0;
            tmp_delay  = 0.0;
            real_delay = 0.0;
        end
        else
            if(adjust == 1'b1)
            begin
                fb_route_delay = clk_fb_first_edge - clk_in_first_edge;
                if((clkin_time > 0) && (fb_route_delay > 0))
                begin
                    tmp_ratio  = fb_route_delay / clkin_time;
                    tmp_delay  = fb_route_delay - (clkin_time * tmp_ratio);
                    real_delay = clkin_time - tmp_delay;
                    adjust <= 1'b0;
                end
            end
    end

    always @(inner_clk)
    begin
        if(EXTERNAL_FB == "CLKOUTF" || EXTERNAL_FB == "CLKOUT0" || EXTERNAL_FB == "CLKOUT1" || EXTERNAL_FB == "CLKOUT2" || EXTERNAL_FB == "CLKOUT3" || EXTERNAL_FB == "CLKOUT4" || EXTERNAL_FB == "CLKOUT5" || EXTERNAL_FB == "CLKOUT6")
            vcoclk <= #real_delay inner_clk;
        else
            vcoclk <= inner_clk;
    end

    always @(*)
    begin
        if(!rst_n)
            new_delay = 0;
        else
            new_delay = (clkin_time * idivider) / mdivider;
    end

    assign #(real_delay + new_delay) adjust_dly = adjust; 
    assign frac_restart = ~adjust & adjust_dly;
///////////////////////////////////////////////////////
////PLL_LOCK///////////////////////////////////////////
    assign clk_lock = (INTERNAL_FB == "DISABLE") ? CLKFB : clk_in;

    always @(posedge clk_lock or negedge rstanalog_n or clk_gate)
    begin
        if(!rstanalog_n)
        begin
            start_clk <= 1'b0;
            cnt_clkfb <= 2'b00;
        end
        else
            if(!clk_gate)
                if(cnt_clkfb == 2'b11)
                    start_clk = 1'b1;
                else
                    cnt_clkfb = cnt_clkfb + 1'b1;
            else
            begin
                start_clk <= 1'b0;
                cnt_clkfb <= 2'b00;
            end
    end

    always @(posedge clk_in or negedge rstanalog_n or clk_gate)
    begin
        if(!rstanalog_n)
        begin
            cnt_lock  <= 8'h1;
            lock_wait <= 1'b0;
        end
        else
            if(!clk_gate && start_clk)
                if(cnt_lock == idivider * 3)
                    lock_wait <= 1'b1;
                else
                    cnt_lock <= cnt_lock + 1'b1;
            else
            begin
                cnt_lock <= 8'h1;
                lock_wait <= 1'b0;
            end
    end

    always @(posedge clk_in or negedge rst_n or clk_gate)
    begin
        if(!rst_n)
            lock_reg <= 1'b0;
        else
            if(LOCK_MODE == 1'b0)
                if(!clk_gate)
                    lock_reg <= lock_wait;
                else
                    lock_reg <= 1'b0;
            else
                lock_reg <= lock_reg | lock_wait;
    end

    assign LOCK = lock_reg;
///////////////////////////////////////////////////////
////DPS////////////////////////////////////////////////
    always @(posedge DPS_CLK or negedge rst_n)
    begin
        if(!rst_n)
        begin
            dps_cnt <= dps_init;
            dps_cnt_finish <= 1'b0;
        end
        else
        begin
            if(div_dps_en == 1'b1 && DPS_EN == 1'b1)
                if(DPS_DIR == 1'b0)
                begin
                    if(dps_cnt < 6'd63)
                        dps_cnt <= dps_cnt + 1'b1;
                    else
                        dps_cnt <= 0;

                    dps_cnt_finish <= 1'b1;
                end
                else
                    if(DPS_DIR == 1'b1)
                    begin
                        if(dps_cnt > 0)
                            dps_cnt <= dps_cnt - 1'b1;
                        else
                            dps_cnt <= 6'd63;

                        dps_cnt_finish <= 1'b1;
                    end

             if(dps_done_reg == 1'b1)
                  dps_cnt_finish <= 1'b0;
        end
    end

    always @(posedge DPS_CLK or negedge rst_n)
    begin
        if(!rst_n)
        begin
            dps_done_cnt <= 1;
            dps_done_reg <= 1'b0;
        end
        else
            if(dps_cnt_finish)
                if(dps_done_cnt < 13)
                begin
                    dps_done_cnt <= dps_done_cnt + 1;
                    dps_done_reg <= 1'b0;
                end
                else
                begin
                    dps_done_cnt <= 0;
                    dps_done_reg <= 1'b1;
                end
    end

    assign DPS_DONE = dps_done_reg;

    assign vcoclk_dps_dly[0] = vcoclk;

    genvar gen_j;

    generate
        for(gen_j=1; gen_j<64; gen_j=gen_j+1'b1)
        begin
            assign #(vcoclk_period/64) vcoclk_dps_dly[gen_j] = vcoclk_dps_dly[gen_j-1];
        end
    endgenerate

    always @(*)
    begin
        if(DPS_DIR == 1'b1)
            vcoclk_dps_adjust = vcoclk_dps_dly[dps_cnt];
        else
            if(dps_cnt == 6'd63)
                vcoclk_dps_adjust = vcoclk_dps_dly[0];
            else
                vcoclk_dps_adjust = vcoclk_dps_dly[dps_cnt + 1];
    end

    always @(negedge vcoclk_dps_adjust or negedge rst_n)
    begin
        if(!rst_n)
        begin
            dps_cnt_dly0 = dps_cnt;
            dps_cnt_dly1 = dps_cnt;
        end
        else
        begin
            dps_cnt_dly0 <= dps_cnt;
            dps_cnt_dly1 <= dps_cnt_dly0;
        end
    end

    assign vcoclk_dps = vcoclk_dps_dly[dps_cnt_dly1];
///////////////////////////////////////////////////////
////PLL_ODIV///////////////////////////////////////////
////ODIV0//////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel0_en)
            case(muxsel0)
                2'b00: odiv0_clkin = vcoclk;
                2'b01: odiv0_clkin = vcoclk_dps;
                default: odiv0_clkin = 1'b0;
            endcase
        else
            odiv0_clkin = 1'b0;
    end

    always @(posedge odiv0_clkin or negedge odiv0_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv0_counter <= 8'h0;
            odiv0_out_reg <= 1'b0;
        end
        else
        begin
            if(divider0 == 8'h1)
            begin
                odiv0_counter <= 8'h0;
                odiv0_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv0_counter < ({divider0, 1'b0} - 1'b1))
                    odiv0_counter <= odiv0_counter + 1'b1;
                else
                    odiv0_counter <= 8'h0;

                if(odiv0_counter < duty0)
                    odiv0_out_reg <= 1'b1;
                else
                    odiv0_out_reg <= 1'b0;
            end
        end
    end

    assign odiv0_int_out = (divider0 == 8'h1) ? odiv0_clkin : odiv0_out_reg;

    assign divider0_frac = ratio0_frac;

    always @(*)
    begin
        if(odiv0_frac_en == 1'b1)
        begin
            odiv0_p_int = divider0 / 2;

            if(!divider0[0])
                if(!divider0_frac[0])
                begin
                    odiv0_hp_frac = divider0_frac / 2;
                    odiv0_lp_frac = divider0_frac / 2;
                end
                else
                begin
                    odiv0_hp_frac = (divider0_frac + 1'b1) / 2;
                    odiv0_lp_frac = divider0_frac / 2;
                end
            else
                if(!divider0_frac[0])
                begin
                    odiv0_hp_frac = divider0_frac / 2 + 3'b100;
                    odiv0_lp_frac = divider0_frac / 2 + 3'b100;
                end
                else
                begin
                    odiv0_hp_frac = divider0_frac / 2 + 3'b101;
                    odiv0_lp_frac = divider0_frac / 2 + 3'b100;
                end
        end
        else
        begin
             odiv0_p_int   = 0;
             odiv0_hp_frac = 0;
             odiv0_lp_frac = 0;
        end
    end

    always @(*)
    begin
        odiv0_frac_hp = vcoclk_period * odiv0_p_int + (vcoclk_period * odiv0_hp_frac) / 8;
        odiv0_frac_lp = vcoclk_period * odiv0_p_int + (vcoclk_period * odiv0_lp_frac) / 8;
    end

    always @(clk_gate or odiv0_frac_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv0_frac_out <= 1'b0;
        else
            if(!clk_gate && odiv0_frac_en && odiv0_dps_en == 1'b0)
            begin
                odiv0_frac_out <= 1'b1;
                for(i = 1; i < 8; i = i+1)
                begin: loop1
                    if(frac_restart)
                    begin
                        #(real_delay);
                        #(odiv0_frac_hp) odiv0_frac_out <= 1'b0;
                        #(odiv0_frac_lp) odiv0_frac_out <= 1'b1;
                    end
                    else
                    begin
                        #(odiv0_frac_hp) odiv0_frac_out <= 1'b0;
                        #(odiv0_frac_lp) odiv0_frac_out <= 1'b1;
                    end
                end
                #(odiv0_frac_hp) odiv0_frac_out <= 1'b0;
                #(odiv0_frac_lp);
                i = 1;
                odiv0_frac_out <= 1'b1;
            end
            else
                odiv0_frac_out <= 1'b0;
    end

    assign odiv0_out = (odiv0_frac_en) ? odiv0_frac_out : odiv0_int_out;
////ODIV1//////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel1_en)
            case(muxsel1)
                2'b00: odiv1_clkin = vcoclk;
                2'b01: odiv1_clkin = vcoclk_dps;
                default: odiv1_clkin = 1'b0;
            endcase
        else
            odiv1_clkin = 1'b0;
    end

    always @(posedge odiv1_clkin or negedge odiv1_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv1_counter <= 8'h0;
            odiv1_out_reg <= 1'b0;
        end
        else
        begin
            if(divider1 == 8'h1)
            begin
                odiv1_counter <= 8'h0;
                odiv1_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv1_counter < ({divider1, 1'b0} - 1'b1))
                    odiv1_counter <= odiv1_counter + 1'b1;
                else
                    odiv1_counter <= 8'h0;

                if(odiv1_counter < duty1)
                    odiv1_out_reg <= 1'b1;
                else
                    odiv1_out_reg <= 1'b0;
            end
        end
    end

    assign odiv1_out = (divider1 == 8'h1) ? odiv1_clkin : odiv1_out_reg;
////ODIV2//////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel2_en)
            case(muxsel2)
                2'b00: odiv2_clkin = vcoclk;
                2'b01: odiv2_clkin = vcoclk_dps;
                default: odiv2_clkin = 1'b0;
            endcase
        else
            odiv2_clkin = 1'b0;
    end

    always @(posedge odiv2_clkin or negedge odiv2_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv2_counter <= 8'h0;
            odiv2_out_reg <= 1'b0;
        end
        else
        begin
            if(divider2 == 8'h1)
            begin
                odiv2_counter <= 8'h0;
                odiv2_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv2_counter < ({divider2, 1'b0} - 1'b1))
                    odiv2_counter <= odiv2_counter + 1'b1;
                else
                    odiv2_counter <= 8'h0;

                if(odiv2_counter < duty2)
                    odiv2_out_reg <= 1'b1;
                else
                    odiv2_out_reg <= 1'b0;
            end
        end
    end

    assign odiv2_out = (divider2 == 8'h1) ? odiv2_clkin : odiv2_out_reg;
////ODIV3//////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel3_en)
            case(muxsel3)
                2'b00: odiv3_clkin = vcoclk;
                2'b01: odiv3_clkin = vcoclk_dps;
                default: odiv3_clkin = 1'b0;
            endcase
        else
            odiv3_clkin = 1'b0;
    end

    always @(posedge odiv3_clkin or negedge odiv3_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv3_counter <= 8'h0;
            odiv3_out_reg <= 1'b0;
        end
        else
        begin
            if(divider3 == 8'h1)
            begin
                odiv3_counter <= 8'h0;
                odiv3_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv3_counter < ({divider3, 1'b0} - 1'b1))
                    odiv3_counter <= odiv3_counter + 1'b1;
                else
                    odiv3_counter <= 8'h0;

                if(odiv3_counter < duty3)
                    odiv3_out_reg <= 1'b1;
                else
                    odiv3_out_reg <= 1'b0;
            end
        end
    end

    assign odiv3_out = (divider3 == 8'h1) ? odiv3_clkin : odiv3_out_reg;
////ODIV4//////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel4_en)
            case(muxsel4)
                2'b00: odiv4_clkin = vcoclk;
                2'b01: odiv4_clkin = vcoclk_dps;
                default: odiv4_clkin = 1'b0;
            endcase
        else
            odiv4_clkin = 1'b0;
    end


    always @(posedge odiv4_clkin or negedge odiv4_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv4_counter <= 8'h0;
            odiv4_out_reg <= 1'b0;
        end
        else
        begin
            if(divider4 == 8'h1)
            begin
                odiv4_counter <= 8'h0;
                odiv4_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv4_counter < ({divider4, 1'b0} - 1'b1))
                    odiv4_counter <= odiv4_counter + 1'b1;
                else
                    odiv4_counter <= 8'h0;

                if(odiv4_counter < duty4)
                    odiv4_out_reg <= 1'b1;
                else
                    odiv4_out_reg <= 1'b0;
            end
        end
    end

    assign odiv4_out = (divider4 == 8'h1) ? odiv4_clkin : odiv4_out_reg;
////odiv5////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel5_en)
            case(muxsel5)
                2'b00: odiv5_clkin = vcoclk;
                2'b01: odiv5_clkin = vcoclk_dps;
                2'b10: odiv5_clkin = odiv6_out;
                default: odiv5_clkin = 1'b0;
            endcase
        else
            odiv5_clkin = 1'b0;
    end

    always @(posedge odiv5_clkin or negedge odiv5_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv5_counter <= 8'h0;
            odiv5_out_reg <= 1'b0;
        end
        else
        begin
            if(divider5 == 8'h1)
            begin
                odiv5_counter <= 8'h0;
                odiv5_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv5_counter < ({divider5, 1'b0} - 1'b1))
                    odiv5_counter <= odiv5_counter + 1'b1;
                else
                    odiv5_counter <= 8'h0;

                if(odiv5_counter < duty5)
                    odiv5_out_reg <= 1'b1;
                else
                    odiv5_out_reg <= 1'b0;
            end
        end
    end

    assign odiv5_out = (divider5 == 8'h1) ? odiv5_clkin : odiv5_out_reg;
////odiv6////////////////////////////////////////////
    always @(*)
    begin
        if(muxsel6_en)
            case(muxsel6)
                2'b00: odiv6_clkin = vcoclk;
                2'b01: odiv6_clkin = vcoclk_dps;
                default: odiv6_clkin = 1'b0;
            endcase
        else
            odiv6_clkin = 1'b0;
    end

    always @(posedge odiv6_clkin or negedge odiv6_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            odiv6_counter <= 8'h0;
            odiv6_out_reg <= 1'b0;
        end
        else
        begin
            if(divider6 == 8'h1)
            begin
                odiv6_counter <= 8'h0;
                odiv6_out_reg <= 1'b0;
            end
            else
            begin
                if(odiv6_counter < ({divider6, 1'b0} - 1'b1))
                    odiv6_counter <= odiv6_counter + 1'b1;
                else
                    odiv6_counter <= 8'h0;

                if(odiv6_counter < duty6)
                    odiv6_out_reg <= 1'b1;
                else
                    odiv6_out_reg <= 1'b0;
            end
        end
    end

    assign odiv6_out = (divider6 == 8'h1) ? odiv6_clkin : odiv6_out_reg;
////FDIV///////////////////////////////////////////////
    always @(*)
    begin
        if(muxself_en)
            case(muxself)
                2'b00: fdiv_clkin = vcoclk;
                2'b01: fdiv_clkin = vcoclk_dps;
                default: fdiv_clkin = 1'b0;
            endcase
        else
            fdiv_clkin = 1'b0;
    end

    always @(posedge fdiv_clkin or negedge fdiv_clkin or negedge rst_n)
    begin
        if(!rst_n)
        begin
            fdiv_counter <= 8'h0;
            fdiv_out_reg <= 1'b0;
        end
        else
        begin
            if(fdivider == 8'h1)
            begin
                fdiv_counter <= 8'h0;
                fdiv_out_reg <= 1'b0;
            end
            else
            begin
                if(fdiv_counter < ({fdivider, 1'b0} - 1'b1))
                    fdiv_counter <= fdiv_counter + 1'b1;
                else
                    fdiv_counter <= 8'h0;

                if(fdiv_counter < dutyf)
                    fdiv_out_reg <= 1'b1;
                else
                    fdiv_out_reg <= 1'b0;
            end
        end
    end

    assign fdiv_int_out = (fdivider == 8'h1) ? fdiv_clkin : fdiv_out_reg;

    assign fdivider_frac = ratiof_frac;

    always @(*)
    begin
        if(fdiv_frac_en == 1'b1)
        begin
            fdiv_p_int = fdivider / 2;

            if(!fdivider[0])
                if(!fdivider_frac[0])
                begin
                    fdiv_hp_frac = fdivider_frac / 2;
                    fdiv_lp_frac = fdivider_frac / 2;
                end
                else
                begin
                    fdiv_hp_frac = fdivider_frac / 2 + 3'b001;
                    fdiv_lp_frac = fdivider_frac / 2;
                end
            else
                if(!fdivider_frac[0])
                begin
                    fdiv_hp_frac = fdivider_frac / 2 + 3'b100;
                    fdiv_lp_frac = fdivider_frac / 2 + 3'b100;
                end
                else
                begin
                    fdiv_hp_frac = fdivider_frac / 2 + 3'b101;
                    fdiv_lp_frac = fdivider_frac / 2 + 3'b100;
                end
        end
        else
        begin
             fdiv_p_int   = 0;
             fdiv_hp_frac = 0;
             fdiv_lp_frac = 0;
        end
    end

    always @(*)
    begin
        fdiv_frac_hp = vcoclk_period * fdiv_p_int + (vcoclk_period * fdiv_hp_frac) / 8;
        fdiv_frac_lp = vcoclk_period * fdiv_p_int + (vcoclk_period * fdiv_lp_frac) / 8;
    end

    always @(clk_gate or fdiv_frac_out or negedge rst_n)
    begin
        if(!rst_n)
            fdiv_frac_out <= 1'b0;
        else
            if(!clk_gate && fdiv_frac_en && fdiv_dps_en == 1'b0)
            begin
                fdiv_frac_out <= 1'b1;
                for(j = 1; j < 8; j = j+1)
                begin: loop2
                    if(frac_restart)
                    begin
                        #(real_delay);
                        #(fdiv_frac_hp) fdiv_frac_out <= 1'b0;
                        #(fdiv_frac_lp) fdiv_frac_out <= 1'b1;
                    end
                    else
                    begin
                        #(fdiv_frac_hp) fdiv_frac_out <= 1'b0;
                        #(fdiv_frac_lp) fdiv_frac_out <= 1'b1;
                    end
                end
                #(fdiv_frac_hp) fdiv_frac_out <= 1'b0;
                #(fdiv_frac_lp);
                j = 1;
                fdiv_frac_out <= 1'b1;
            end
            else
                fdiv_frac_out <= 1'b0;
    end

    assign fdiv_out = (fdiv_frac_en) ? fdiv_frac_out : fdiv_int_out;
///////////////////////////////////////////////////////
////PHASE_SHIFT////////////////////////////////////////
    always @(*)
    begin
        if(clkout0_time > 0 && odiv0_dps_en == 1'b0)
            vco_fphase_delay0 <= (odiv0_fphase * clkout0_time) / (8 * divider0);
        else
            vco_fphase_delay0 <= 0.0;

        if(clkout1_time > 0 && odiv1_dps_en == 1'b0)
            vco_fphase_delay1 <= (odiv1_fphase * clkout1_time) / (8 * divider1);
        else
            vco_fphase_delay1 <= 0.0;

        if(clkout2_time > 0 && odiv2_dps_en == 1'b0)
            vco_fphase_delay2 <= (odiv2_fphase * clkout2_time) / (8 * divider2);
        else
            vco_fphase_delay2 <= 0.0;

        if(clkout3_time > 0 && odiv3_dps_en == 1'b0)
            vco_fphase_delay3 <= (odiv3_fphase * clkout3_time) / (8 * divider3);
        else
            vco_fphase_delay3 <= 0.0;

        if(clkout4_time > 0 && odiv4_dps_en == 1'b0)
            vco_fphase_delay4 <= (odiv4_fphase * clkout4_time) / (8 * divider4);
        else
            vco_fphase_delay4 <= 0.0;

        if(clkout5_time > 0 && odiv5_dps_en == 1'b0)
            vco_fphase_delay5 <= (odiv5_fphase * clkout5_time) / (8 * divider5);
        else
            vco_fphase_delay5 <= 0.0;

        if(clkout6_time > 0 && odiv6_dps_en == 1'b0)
            vco_fphase_delay6 <= (odiv6_fphase * clkout6_time) / (8 * divider6);
        else
            vco_fphase_delay6 <= 0.0;

        if(clkoutf_time > 0 && fdiv_dps_en == 1'b0)
            vco_fphase_delayf <= (fdiv_fphase * clkoutf_time) / (8 * fdivider);
        else
            vco_fphase_delayf <= 0.0;
    end

    always @(*)
    begin
        if(divider0 > odiv0_cphase)
            cphase0 = odiv0_cphase;
        else
            cphase0 = odiv0_cphase - (odiv0_cphase / divider0) * divider0;

        if(divider1 > odiv1_cphase)
            cphase1 = odiv1_cphase;
        else
            cphase1 = odiv1_cphase - (odiv1_cphase / divider1) * divider1;

        if(divider2 > odiv2_cphase)
            cphase2 = odiv2_cphase;
        else
            cphase2 = odiv2_cphase - (odiv2_cphase / divider2) * divider2;

        if(divider3 > odiv3_cphase)
            cphase3 = odiv3_cphase;
        else
            cphase3 = odiv3_cphase - (odiv3_cphase / divider3) * divider3;

        if(divider4 > odiv4_cphase)
            cphase4 = odiv4_cphase;
        else
            cphase4 = odiv4_cphase - (odiv4_cphase / divider4) * divider4;

        if(divider5 > odiv5_cphase)
            cphase5 = odiv5_cphase;
        else
            cphase5 = odiv5_cphase - (odiv5_cphase / divider5) * divider5;

        if(divider6 > odiv6_cphase)
            cphase6 = odiv6_cphase;
        else
            cphase5 = odiv6_cphase - (odiv6_cphase / divider6) * divider6;

        if(fdivider > fdiv_cphase)
            cphasef = fdiv_cphase;
        else
            cphasef = fdiv_cphase - (fdiv_cphase / fdivider) * fdivider;
    end

    always @(*)
    begin
        if(clkout0_time > 0)
            cphase_delay0 <= clkout0_time - (((divider0 - cphase0) * clkout0_time) / divider0);
        else
            cphase_delay0 <= 0.0;

        if(clkout1_time > 0)
            cphase_delay1 <= clkout1_time - (((divider1 - cphase1) * clkout1_time) / divider1);
        else
            cphase_delay1 <= 0.0;

        if(clkout2_time > 0)
            cphase_delay2 <= clkout2_time - (((divider2 - cphase2) * clkout2_time) / divider2);
        else
            cphase_delay2 <= 0.0;

        if(clkout3_time > 0)
            cphase_delay3 <= clkout3_time - (((divider3 - cphase3) * clkout3_time) / divider3);
        else
            cphase_delay3 <= 0.0;

        if(clkout4_time > 0)
            cphase_delay4 <= clkout4_time - (((divider4 - cphase4) * clkout4_time) / divider4);
        else
            cphase_delay4 <= 0.0;

        if(clkout5_time > 0)
            cphase_delay5 <= clkout5_time - (((divider5 - cphase5) * clkout5_time) / divider5);
        else
            cphase_delay5 <= 0.0;

        if(clkout6_time > 0)
            cphase_delay6 <= clkout6_time - (((divider6 - cphase6) * clkout6_time) / divider6);
        else
            cphase_delay6 <= 0.0;

        if(clkoutf_time > 0)
            cphase_delayf <= clkoutf_time - (((fdivider - cphasef) * clkoutf_time) / fdivider);
        else
            cphase_delayf <= 0.0;
    end
////PHASE_SHIFT_DLY////////////////////////////////////
    always @(odiv0_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv0_out_delay1 <= 1'b0;
        else
            odiv0_out_delay1 <= #vco_fphase_delay0 odiv0_out;
    end

    always @(odiv0_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv0_out_delay <= 1'b0;
        else
            odiv0_out_delay <= #cphase_delay0 odiv0_out_delay1;
    end

    always @(odiv1_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv1_out_delay1 <= 1'b0;
        else
            odiv1_out_delay1 <= #vco_fphase_delay1 odiv1_out;
    end

    always @(odiv1_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv1_out_delay <= 1'b0;
        else
            odiv1_out_delay <= #cphase_delay1 odiv1_out_delay1;
    end

    always @(odiv2_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv2_out_delay1 <= 1'b0;
        else
            odiv2_out_delay1 <= #vco_fphase_delay2 odiv2_out;
    end

    always @(odiv2_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv2_out_delay <= 1'b0;
        else
            odiv2_out_delay <= #cphase_delay2 odiv2_out_delay1;
    end

    always @(odiv3_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv3_out_delay1 <= 1'b0;
        else
            odiv3_out_delay1 <= #vco_fphase_delay3 odiv3_out;
    end

    always @(odiv3_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv3_out_delay <= 1'b0;
        else
            odiv3_out_delay <= #cphase_delay3 odiv3_out_delay1;
    end

    always @(odiv4_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv4_out_delay1 <= 1'b0;
        else
            odiv4_out_delay1 <= #vco_fphase_delay4 odiv4_out;
    end

    always @(odiv4_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv4_out_delay <= 1'b0;
        else
            odiv4_out_delay <= #cphase_delay4 odiv4_out_delay1;
    end

    always @(odiv5_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv5_out_delay1 <= 1'b0;
        else
            odiv5_out_delay1 <= #vco_fphase_delay5 odiv5_out;
    end

    always @(odiv5_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv5_out_delay <= 1'b0;
        else
            odiv5_out_delay <= #cphase_delay5 odiv5_out_delay1;
    end

    always @(odiv6_out or negedge rst_n)
    begin
        if(!rst_n)
            odiv6_out_delay1 <= 1'b0;
        else
            odiv6_out_delay1 <= #vco_fphase_delay6 odiv6_out;
    end

    always @(odiv6_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            odiv6_out_delay <= 1'b0;
        else
            odiv6_out_delay <= #cphase_delay6 odiv6_out_delay1;
    end

    always @(fdiv_out or negedge rst_n)
    begin
        if(!rst_n)
            fdiv_out_delay1 <= 1'b0;
        else
            fdiv_out_delay1 <= #vco_fphase_delayf fdiv_out;
    end

    always @(fdiv_out_delay1 or negedge rst_n)
    begin
        if(!rst_n)
            fdiv_out_delay <= 1'b0;
        else
            fdiv_out_delay <= #cphase_delayf fdiv_out_delay1;
    end
///////////////////////////////////////////////////////
////PLL_GATE///////////////////////////////////////////
    assign clkout0_gate = (CLKOUT0_SYN_EN == "TRUE") ? CLKOUT0_SYN : 1'b0;

    always @(negedge odiv0_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out0_gate <= 3'b000;
        else
            clk_out0_gate <= {clk_out0_gate[1:0], ~clkout0_gate};
    end

    assign CLKOUT0  = odiv0_out_delay & clk_out0_gate[2];
    assign CLKOUT0N = ~CLKOUT0;

    assign clkout1_gate = (CLKOUT1_SYN_EN == "TRUE") ? CLKOUT1_SYN : 1'b0;

    always @(negedge odiv1_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out1_gate <= 3'b000;
        else
            clk_out1_gate <= {clk_out1_gate[1:0], ~clkout1_gate};
    end

    assign CLKOUT1  = odiv1_out_delay & clk_out1_gate[2];
    assign CLKOUT1N = ~CLKOUT1;

    assign clkout2_gate = (CLKOUT2_SYN_EN == "TRUE") ? CLKOUT2_SYN : 1'b0;

    always @(negedge odiv2_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out2_gate <= 3'b000;
        else
            clk_out2_gate <= {clk_out2_gate[1:0], ~clkout2_gate};
    end

    assign CLKOUT2  = odiv2_out_delay & clk_out2_gate[2];
    assign CLKOUT2N = ~CLKOUT2;

    assign clkout3_gate = (CLKOUT3_SYN_EN == "TRUE") ? CLKOUT3_SYN : 1'b0;

    always @(negedge odiv3_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out3_gate <= 3'b000;
        else
            clk_out3_gate <= {clk_out3_gate[1:0], ~clkout3_gate};
    end

    assign CLKOUT3  = odiv3_out_delay & clk_out3_gate[2];
    assign CLKOUT3N = ~CLKOUT3;

    assign clkout4_gate = (CLKOUT4_SYN_EN == "TRUE") ? CLKOUT4_SYN : 1'b0;

    always @(negedge odiv4_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out4_gate <= 3'b000;
        else
            clk_out4_gate <= {clk_out4_gate[1:0], ~clkout4_gate};
    end

    assign CLKOUT4 = odiv4_out_delay & clk_out4_gate[2];

    assign clkout5_gate = (CLKOUT5_SYN_EN == "TRUE") ? CLKOUT5_SYN : 1'b0;

    always @(negedge odiv5_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out5_gate <= 3'b000;
        else
            clk_out5_gate <= {clk_out5_gate[1:0], ~clkout5_gate};
    end

    assign CLKOUT5 = odiv5_out_delay & clk_out5_gate[2];

    assign clkout6_gate = (CLKOUT6_SYN_EN == "TRUE") ? CLKOUT6_SYN : 1'b0;

    always @(negedge odiv6_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_out6_gate <= 3'b000;
        else
            clk_out6_gate <= {clk_out6_gate[1:0], ~clkout6_gate};
    end

    assign CLKOUT6 = odiv6_out_delay & clk_out6_gate[2];

    assign clkoutf_gate = (CLKOUTF_SYN_EN == "TRUE") ? CLKOUTF_SYN: 1'b0;

    always @(negedge fdiv_out_delay or negedge rst_n)
    begin
        if(!rst_n)
            clk_outf_gate <= 3'b000;
        else
            clk_outf_gate <= {clk_outf_gate[1:0], ~clkoutf_gate};
    end

    assign CLKOUTF  = fdiv_out_delay & clk_outf_gate[2];
    assign CLKOUTFN = ~CLKOUTF;
///////////////////////////////////////////////////////
////APB////////////////////////////////////////////////
    always @(posedge APB_CLK or negedge APB_RST_N)
    begin
       if(!APB_RST_N)
           apb_rstn_sync <= 2'b00;
       else
           apb_rstn_sync <= {apb_rstn_sync[0], 1'b1};
    end

    always @(posedge APB_CLK or negedge apb_rstn_sync[1])
    begin
        if(!apb_rstn_sync[1])
            ready <= 1'b0;
        else
            if(APB_SEL && !APB_EN)
                ready <= 1'b1;
            else
                ready <= 1'b0;
    end

    always @(posedge APB_CLK)
    begin
        if(APB_WRITE && APB_SEL && APB_EN)
            case(APB_ADDR)
                5'h0 : mem0  <= APB_WDATA;
                5'h1 : mem1  <= APB_WDATA;
                5'h2 : mem2  <= APB_WDATA[5:0];
                5'h3 : mem3  <= APB_WDATA;
                5'h4 : mem4  <= APB_WDATA[12:0];
                5'h5 : mem5  <= APB_WDATA;
                5'h6 : mem6  <= APB_WDATA[12:0];
                5'h7 : mem7  <= APB_WDATA;
                5'h8 : mem8  <= APB_WDATA[12:0];
                5'h9 : mem9  <= APB_WDATA;
                5'hA : mem10 <= APB_WDATA[12:0];
                5'hB : mem11 <= APB_WDATA;
                5'hC : mem12 <= APB_WDATA[12:0];
                5'hD : mem13 <= APB_WDATA;
                5'hE : mem14 <= APB_WDATA[12:0];
                5'hF : mem15 <= APB_WDATA;
                5'h10: mem16 <= APB_WDATA;
                5'h11: mem17 <= APB_WDATA[5:0];
                5'h12: mem18 <= APB_WDATA[7:0];
                5'h13: mem19 <= APB_WDATA[7:0];
                5'h14: mem20 <= APB_WDATA[13:0];
                5'h15: mem21 <= APB_WDATA[5:0];
            endcase
    end

    always @(posedge APB_CLK or negedge apb_rstn_sync[1])
    begin
        if(!apb_rstn_sync[1])
            rdata <= 16'h0;
        else
            if(!APB_WRITE && APB_SEL && !APB_EN)
                case(APB_ADDR)
                    5'h0 : rdata <= mem0;
                    5'h1 : rdata <= mem1;
                    5'h2 : rdata <= mem2;
                    5'h3 : rdata <= mem3;
                    5'h4 : rdata <= mem4;
                    5'h5 : rdata <= mem5;
                    5'h6 : rdata <= mem6;
                    5'h7 : rdata <= mem7;
                    5'h8 : rdata <= mem8;
                    5'h9 : rdata <= mem9;
                    5'hA : rdata <= mem10;
                    5'hB : rdata <= mem11;
                    5'hC : rdata <= mem12;
                    5'hD : rdata <= mem13;
                    5'hE : rdata <= mem14;
                    5'hF : rdata <= mem15;
                    5'h10: rdata <= mem16;
                    5'h11: rdata <= mem17;
                    5'h12: rdata <= mem18;
                    5'h13: rdata <= mem19;
                    5'h14: rdata <= mem20;
                    5'h15: rdata <= mem21;
                endcase
            else
                rdata <= 16'h0;
    end

    assign APB_READY = ready;
    assign APB_RDATA = rdata;
endmodule
