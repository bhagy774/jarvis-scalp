# Advanced Options Hedging & Greeks Knowledge Base

## 1. Core Greeks Overview
*   **Delta:** The rate of change of the option's price with respect to a $1 change in the underlying asset. Ranges from 0 to 1 (Calls) and -1 to 0 (Puts). Also represents the approximate probability of the option expiring in-the-money (ITM).
*   **Gamma:** The rate of change of Delta. Gamma is highest for At-The-Money (ATM) options and options close to expiration. It acts as the "acceleration" of Delta.
*   **Theta:** Time decay. The amount the option price decreases every day. Highest for ATM options.
*   **Vega:** Sensitivity to Implied Volatility (IV). The amount the option price changes for a 1% change in IV. Highest for long-term options.

## 2. Advanced Greeks (Second and Third Order)
*   **Vanna:** The rate of change of Delta with respect to a 1% change in Implied Volatility. If IV drops, OTM options lose Delta quickly (they become less likely to end up ITM).
*   **Charm (Delta Bleed):** The rate of change of Delta with respect to time passing (Theta). As expiration approaches, OTM options see their Delta drop towards 0, while ITM options see their Delta climb towards 100.
*   **Vomma:** The rate of change of Vega with respect to changes in IV. High when IV is volatile.

## 3. Institutional Hedging Strategies
*   **Delta-Neutral Portfolio:** A portfolio constructed so that the net Delta is zero. The trader makes money not on price direction, but on Volatility (Vega) or Time Decay (Theta).
*   **Gamma Scalping:** A delta-neutral strategy where a trader buys options (Long Gamma) and continually buys/sells the underlying asset as price moves to keep the Delta at zero. The profits from trading the underlying offset the Theta decay of the options.
*   **Iron Condor:** Selling an OTM Call spread and an OTM Put spread. Profitable in sideways, low-volatility regimes.
*   **Short Straddle:** Selling an ATM Call and ATM Put. Extremely sensitive to Gamma risk, but collects massive Theta. Used when the market is expected to stay completely flat.

## 4. Volatility Dynamics
*   **IV Crush:** A massive drop in Implied Volatility immediately after a known binary event (like earnings or a Fed meeting). Long option holders lose massive value due to Vega collapse, even if they got the price direction right.
*   **Volatility Smile/Skew:** OTM Puts typically have higher IV than equidistant OTM Calls because institutions buy OTM Puts as insurance against market crashes, driving up their premium.
