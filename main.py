# region imports
from AlgorithmImports import *
# endregion

# Based on the paper "Global momentum: The optimal trading approach", by Alain Wouassom, Yaz Gülnur Muradoğlu, and Nicholas Tsitsianis
class CrawlingBrownWolf(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2016, 10, 1)
        self.set_cash(100_000)
        self.set_benchmark("URTH") # MCSI Benchmark ETF

        # Enable seed prices for reliable momentum calculation
        self.settings.seed_initial_prices = True
        
        # Universe of country and regional ETFs
        self._etf_universe = [
            # "SPY",  # S&P 500 (US Large Cap)
            "QQQ",  # Nasdaq 100 (US Tech)
            "IWM",  # Russell 2000 (US Small Cap)
            #"EFA",  # EAFE (Developed Markets ex-US)
            #"EEM",  # Emerging Markets
            #"VGK",  # European Markets
            "EWJ",  # Japan
            "EWG",  # Germany
            "EWU",  # United Kingdom
            "EWC",  # Canada
            "EWA",  # Australia
            "EWH",  # Hong Kong
            "EWT",  # Taiwan
            "EWZ",  # Brazil
            #"FXI",  # China Large Cap - last of original
            "EWO",  # Austria
            "EWK",  # Belgium
            "EWQ",  # France
            "EWI",  # Italy
            "EWN",  # Netherlands
            "EWS",  # Singapore
            "EWP",  # Spain
            "EWD",  # Sweden
            "EWL",  # Switzerland
            "EFNL", # Finland
            "EDEN", # Denmark
            "ENOR", # Norway
            "EIRL", # Ireland
            "EIS",  # Israel
            "INDA", # India
            "EIDO", # Indonesia
            "EWM",  # Malaysia
            "EWW", # Mexico
            "ECH", # Chile
            "MCHI", # China
            "EPU", # Peru
            "THD", # Thailand
            "TUR", # Turkey
            "KSA", # Saudi Arabia
            "QAT", # Qatar
            "UAE", # UAE
            "EZA", # South Africa
            "ARGT", # Argentina
            "EWY" # South Korea
        ]
        
        # Add ETFs to algorithm
        self._symbols = {}
        for ticker in self._etf_universe:
            symbol = self.add_equity(ticker, Resolution.DAILY).symbol
            self._symbols[ticker] = symbol
        
        # Schedule monthly rebalancing on the first trading day of each month
        self.schedule.on(self.date_rules.month_start("SPY"), 
                        self.time_rules.after_market_open("SPY", 30), 
                        self._rebalance)
        
        # Parameters
        self._momentum_period = 126  # Approximately 6 months of trading days
        self._top_n_mom = 10 # Momenturm Filter 
        self._top_n_id = 5 # ID Filter, Number of ETFs to hold
        
    def _rebalance(self):
        """Monthly rebalancing to top momentum ETFs"""
        
        # Calculate momentum for each ETF
        momentum_data = []
        
        for ticker, symbol in self._symbols.items():
            # Get historical prices for momentum calculation
            history = self.history(symbol, self._momentum_period + 1, Resolution.DAILY)
            
            if history.empty or len(history) < self._momentum_period + 1:
                continue
                
            # Calculate momentum as price change over the period
            current_price = history['close'].iloc[-1]
            past_price = history['close'].iloc[0]
            momentum = (current_price - past_price) / past_price

            # Calculate momentum path
            # Da, Gurun, Warachka (2014) information discreteness (ID)
            pos_count = 0
            neg_count = 0
            for day in history.itertuples():
                day_return = day.close - day.open
                if day_return > 0:
                    pos_count += 1
                else:
                    neg_count += 1
            total = len(history)
            id_score = np.sign(momentum) * (neg_count / total - pos_count / total)

            momentum_data.append({
                'symbol': symbol,
                'momentum': momentum,
                'ticker': ticker,
                'ID': id_score
            })
        
        # Sort by momentum (descending)
        momentum_data.sort(key=lambda x: x['momentum'], reverse=True)
        
        # Select top N momentum ETFs
        top_mom_etfs = momentum_data[:self._top_n_mom]
        
        # sort by ID ascending - favors continuous-information names (Da, Gurun, Warachka 2014)
        top_id_etfs = sorted(top_mom_etfs, key=lambda x: x['ID'], reverse=False)
        # Select top N ID ETFs
        top_etfs = top_id_etfs[:self._top_n_id]

        # Log selected ETFs
        self.debug(f"Month: {self.time.strftime('%Y-%m')}")
        for i, etf in enumerate(top_etfs, 1):
            self.debug(f"  {i}. {etf['ticker']}: {etf['momentum']:.2%} momentum, {etf['ID']:.2%} ID")
        
        # Sell ETFs that are no longer in the top list (fills at the close)
        selected_symbols = {etf['symbol'] for etf in top_etfs}
        for symbol in self._symbols.values():
            if symbol not in selected_symbols and self.portfolio[symbol].invested:
                self.market_on_close_order(symbol, -self.portfolio[symbol].quantity,
                                           tag="Dropped from top ETFs")

        # Reallocate the remaining cash equally across the top ETFs (fills at the close)
        weight = 1.0 / len(top_etfs) if top_etfs else 0
        for etf in top_etfs:
            qty = self.calculate_order_quantity(etf['symbol'], weight)
            if qty > 0:
                self.market_on_close_order(etf['symbol'], qty,
                                           tag="Reallocate to equal weight")
