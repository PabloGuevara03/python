# connectors.py
import math
import pandas as pd
from colorama import Fore, Style
from binance.client import Client
from binance.exceptions import BinanceAPIException

class BinanceClient:
    def __init__(self, config):
        self.cfg = config
        self.client = Client(self.cfg.API_KEY, self.cfg.API_SECRET, testnet=(self.cfg.MODE == 'TESTNET'))
        self.step_size = None  # Para cantidad (Lot Size)
        self.tick_size = None  # Para precio (Price Filter)
        self._cache_velas = {} 

    def inicializar(self):
        try:
            self.client.futures_ping()
            print(f"{Fore.GREEN}[BINANCE] Conexión Futuros {self.cfg.MODE} OK.{Style.RESET_ALL}")
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
            found = False
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    for f in s['filters']:
                        # Capturamos Step Size (Cantidad)
                        if f['filterType'] == 'LOT_SIZE':
                            self.step_size = float(f['stepSize'])
                        # Capturamos Tick Size (Precio) - NUEVO
                        if f['filterType'] == 'PRICE_FILTER':
                            self.tick_size = float(f['tickSize'])
                    
                    if self.step_size and self.tick_size:
                        print(f"[INFO] Reglas {symbol}: Step={self.step_size}, Tick={self.tick_size}")
                        found = True
                    break
            if not found: print(f"[WARN] No se encontró info completa para {symbol}")
        except Exception as e:
            print(f"[WARN] Error cargando reglas: {e}")

    def _redondear_precio(self, precio):
        """Ajusta el precio al tick_size exacto de Binance y devuelve string."""
        if not self.tick_size: return "{:.2f}".format(precio) # Fallback
        
        # Lógica de precisión dinámica
        precision = int(round(-math.log(self.tick_size, 10), 0))
        # Redondeo seguro usando formato string
        return "{:.{}f}".format(precio, precision)

    def _configurar_cuenta(self):
        if self.cfg.MODE == 'SIMULATION': return
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
            # CORRECCIÓN: Usar el formateador de precio dinámico
            precio_final = self._redondear_precio(stop_price)
            
            return self.client.futures_create_order(
                symbol=self._formatear_simbolo(),
                side=side,
                positionSide=position_side,
                type=tipo,
                stopPrice=precio_final,  # Enviamos string formateado
                quantity=quantity,
                timeInForce='GTC',
                reduceOnly=True,
                workingType='MARK_PRICE'
            )
        except Exception as e:
            # Imprimir el error exacto es vital para debug
            print(f"{Fore.RED}[ERROR API] {tipo} rechazado ({stop_price}): {e}{Style.RESET_ALL}")
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

    def obtener_velas(self, timeframe=None, limit=None):
        try:
            if timeframe is None: timeframe = self.cfg.TF_SCALP
            init_limit = 200 
            update_limit = 5 
            if timeframe not in self._cache_velas:
                req_limit = init_limit; is_update = False
            else:
                req_limit = update_limit; is_update = True

            k = self.client.futures_klines(symbol=self._formatear_simbolo(), interval=timeframe, limit=req_limit)
            new_df = pd.DataFrame(k, columns=['ts','open','high','low','close','volume','x','y','z','w','v','u'])
            new_df = new_df[['ts','open','high','low','close','volume']]
            new_df['timestamp'] = pd.to_datetime(new_df['ts'], unit='ms')
            cols_float = ['open','high','low','close','volume']
            new_df[cols_float] = new_df[cols_float].astype(float)

            if not is_update:
                self._cache_velas[timeframe] = new_df
            else:
                old_df = self._cache_velas[timeframe]
                combined = pd.concat([old_df, new_df]).drop_duplicates(subset=['ts'], keep='last')
                if len(combined) > 500: combined = combined.iloc[-500:]
                self._cache_velas[timeframe] = combined.sort_values('ts').reset_index(drop=True)
            return self._cache_velas[timeframe]

        except Exception as e:
            print(f"Error Velas ({timeframe}): {e}")
            return self._cache_velas.get(timeframe, pd.DataFrame())

    def obtener_posicion_abierta(self):
        try:
            info = self.client.futures_position_information(symbol=self._formatear_simbolo())
            if info:
                for pos in info:
                    if float(pos['positionAmt']) != 0: return pos
            return None
        except: return None

class MockClient:
    def __init__(self, config): pass
    def inicializar(self): pass