module voice(
    input clk,              // 100MHz System Clock
    input rx_serial,        // UART RX from Laptop
    output reg servo,       // Servo control output
    output led_check        // DEBUG: LED will light up when Unlocked
    );

    // --------------------------------------------------
    // 1. PARAMETERS
    // --------------------------------------------------
    parameter CLK_FREQ  = 100000000;
    parameter BAUD_RATE = 9600;

    // Servo PWM (50Hz -> 20ms period)
    localparam CNT_MAX = 2000000;   // (100MHz / 50Hz)
    localparam CNT_0   = 100000;    // 1ms (0 degrees)
    localparam CNT_90  = 200000;    // 2ms (180 degrees - adjust if needed)

    // UART Bit Timing
    localparam BIT_TIME = CLK_FREQ / BAUD_RATE; // 10416 clock cycles @ 9600 baud

    // --------------------------------------------------
    // 2. INTERNAL REGISTERS & SYNCHRONIZATION
    // --------------------------------------------------
    reg [31:0] counter = 0;
    reg [31:0] duty_cycle = CNT_0;

    // Synchronize the external RX signal to the FPGA clock domain
    reg rx_sync1, rx_sync2;
    always @(posedge clk) begin
        rx_sync1 <= rx_serial;
        rx_sync2 <= rx_sync1;
    end

    // UART Receiver State Machine
    reg [31:0] baud_timer = 0;
    reg [3:0]  bit_idx = 0;
    reg [8:0]  rx_shifter = 0; // Stores Start + 8 Data bits
    reg        rx_busy = 0;

    // --------------------------------------------------
    // 3. MAIN LOGIC
    // --------------------------------------------------
    always @(posedge clk) begin

        // --- A. SERVO PWM GENERATION ---
        if (counter < CNT_MAX - 1)
            counter <= counter + 1;
        else
            counter <= 0;

        servo <= (counter < duty_cycle) ? 1 : 0;

        // --- B. UART RECEIVER (MID-BIT SAMPLING) ---
        if (!rx_busy) begin
            if (rx_sync2 == 0) begin // Start bit detected (falling edge)
                rx_busy    <= 1;
                baud_timer <= 0;
                bit_idx    <= 0;
            end
        end
        else begin
            if (baud_timer < BIT_TIME - 1) begin
                baud_timer <= baud_timer + 1;

                // SAMPLE AT THE MIDDLE OF THE BIT
                if (baud_timer == BIT_TIME / 2) begin
                    rx_shifter[bit_idx] <= rx_sync2;
                end
            end
            else begin
                baud_timer <= 0;
                if (bit_idx < 9) begin
                    bit_idx <= bit_idx + 1;
                end
                else begin
                    rx_busy <= 0;

                    // --- C. DECISION LOGIC (ASCII Check) ---
                    // rx_shifter[0] is Start Bit
                    // rx_shifter[8:1] is the 8-bit Data
                    if (rx_shifter[8:1] == 8'h31) begin        // ASCII '1'
                        duty_cycle <= CNT_90;
                    end
                    else if (rx_shifter[8:1] == 8'h30) begin   // ASCII '0'
                        duty_cycle <= CNT_0;
                    end
                end
            end
        end
    end

    // DEBUG: Assign LED to show if the servo is in "Unlock" mode
    assign led_check = (duty_cycle == CNT_90);

endmodule
