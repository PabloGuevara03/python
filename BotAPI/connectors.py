# connectors.py
import pandas as pd
from colorama import Fore, Style
from binance.client import Client
from binance.exceptions import BinanceAPIException

class BinanceClient:
    def __init__(self, config):
        self.cfg = config
        self.client = Client(self.cfg.API_KEY, self.cfg.API_SECRET, testnet=True)
        self.step_size = None 

    def inicializar(self):
        try:
            self.client.futures_ping()
            print(f"{Fore.GREEN}[BINANCE] Conexión Futuros Testnet OK.{Style.RESET_ALL}")
            self._cargar_reglas_simbolo()
            self._configurar_cuenta()
        except BinanceAPIException as e:
            print(f"{Fore.RED}[ERROR CRÍTICO] Fallo conexión: {e}{Style.RESET_ALL}")

    def _formatear_simbolo(self):
        return self.cfg.SYMBOL.replace('/', '')

    def _cargar_reglas_simbolo(self):
        try:
            info = self.client.futures_exchange_info()
            symbol = self._formatear_simbolo()
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    for f in s['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            self.step_size = float(f['stepSize'])
                            print(f"[INFO] Step Size: {self.step_size}")
                            break
        except Exception as e:
            print(f"[WARN] Error cargando reglas: {e}")

    def _configurar_cuenta(self):
        symbol = self._formatear_simbolo()
        try: self.client.futures_change_position_mode(dualSidePosition=True)
        except: pass
        try:
            self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
            self.client.futures_change_leverage(symbol=symbol, leverage=self.cfg.LEVERAGE)
        except: pass

    def colocar_orden_market(self, side, quantity, position_side):
        try:
            return self.client.futures_create_order(
                symbol=self._formatear_simbolo(),
                side=side,
                positionSide=position_side,
                type='MARKET',
                quantity=quantity
            )
        except Exception as e:
            print(f"{Fore.RED}[ERROR API] Market Order: {e}{Style.RESET_ALL}")
            return None

    def colocar_orden_sl_tp(self, side, quantity, stop_price, position_side, tipo):
        try:
            return self.client.futures_create_order(
                symbol=self._formatear_simbolo(),
                side=side,
                positionSide=position_side,
                type=tipo,
                stopPrice=stop_price,
                quantity=quantity,
                timeInForce='GTC',
                reduceOnly=True
            )
        except Exception as e:
            print(f"{Fore.RED}[ERROR API] Protection Order: {e}{Style.RESET_ALL}")
            return None

    def cancelar_orden(self, order_id):
        try:
            self.client.futures_cancel_order(symbol=self._formatear_simbolo(), orderId=order_id)
            return True
        except: return False

    def obtener_precio_real(self):
        try:
            return float(self.client.futures_symbol_ticker(symbol=self._formatear_simbolo())['price'])
        except: return None

    def obtener_velas(self, timeframe=None, limit=100):
        try:
            if timeframe is None: timeframe = self.cfg.TIMEFRAME_LIVE
            limit_safe = int(limit) if limit else 100
            
            k = self.client.futures_klines(symbol=self._formatear_simbolo(), interval=timeframe, limit=limit_safe)
            df = pd.DataFrame(k, columns=['ts','open','high','low','close','volume','x','y','z','w','v','u'])
            df = df[['ts','open','high','low','close','volume']]
            df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
            for c in ['open','high','low','close','volume']: df[c] = df[c].astype(float)
            return df
        except Exception as e:
            print(f"Error Velas ({timeframe}): {e}")
            return pd.DataFrame()

class MockClient:
    def __init__(self, config): self.step_size = 0.001
    def inicializar(self): pass
    def tick(self): pass
    def obtener_velas(self, tf=None): return pd.DataFrame()
    def obtener_precio_real(self): return 100.0
    def colocar_orden_market(self, *a): return {'orderId': 123}