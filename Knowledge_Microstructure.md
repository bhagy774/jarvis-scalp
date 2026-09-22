# Market Microstructure & High-Frequency Dynamics

## 1. Limit Order Book (LOB) Dynamics
*   **Bid-Ask Spread:** The difference between the highest limit buy order (Bid) and the lowest limit sell order (Ask). A tight spread indicates high liquidity.
*   **Market Depth:** The total volume of limit orders resting at various price levels away from the current price. Thick order books prevent fast price movements; thin order books lead to rapid price spikes/crashes.
*   **Order Book Sweeping:** When a massive market order consumes all limit orders at the best price and "sweeps" through several price levels, causing instant slippage.

## 2. High-Frequency Trading (HFT) Concepts
*   **Latency Arbitrage:** HFT algorithms exploit microsecond differences in price feeds between two different exchanges to buy low on one and instantly sell high on another.
*   **Market Making:** Algorithms that simultaneously quote both bids and asks, profiting from the spread. They rely on high volume and staying delta-neutral.
*   **Front-Running (Legal via HFT):** HFT algorithms detect a large institutional order coming in and use their superior speed to buy the asset milliseconds before the large order executes, then sell it back to the institution at a slightly higher price.
*   **Ping Orders:** HFT algorithms send tiny 1-lot orders inside the spread to "ping" and discover hidden limit orders (Icebergs) before executing larger trades.

## 3. Trade Execution & Slippage
*   **Iceberg Orders:** Large institutional orders broken down into smaller, hidden pieces. Only the "tip of the iceberg" is visible on the order book. When that piece is filled, the next piece instantly appears.
*   **Slippage:** The difference between the expected price of a trade and the price at which the trade is actually executed. Worst during high volatility or in thin markets.
*   **Fill-or-Kill (FOK):** An order type that must be executed immediately and in its entirety, or canceled completely. Used to prevent partial fills.

## 4. Tick-Level Momentum
*   **Tick Flow:** Tracking every single executed trade (Time and Sales). 
*   **Tape Reading:** Analyzing the speed, size, and side (Bid vs Ask) of executed trades on the tape. A rapid succession of large green prints on the Ask indicates aggressive buyer dominance.
