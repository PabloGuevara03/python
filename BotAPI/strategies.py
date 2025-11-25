# strategies.py
import csv
import os
import time
import keyboard
import threading
from datetime import datetime
from colorama import Fore, Style
import utils
import pandas as pd

class TradingStats:
    """Motor de estadísticas para el reporte final."""
    def __init__(self):
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.longs = 0
        self.shorts = 0
        self.scalp_ops = 0
        self.swing_ops = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.trade_history = []
        self.start_time = datetime.now()

    def registrar(self, tipo, pnl, estrategia):
        self.total_trades += 1
        
        # Conteo Long/Short
        if tipo == 'LONG': self.longs += 1
        else: self.shorts += 1
        
        # Conteo Estrategia
        if estrategia == 'SCALP': self.scalp_ops += 1
        elif estrategia == 'SWING': self.swing_ops += 1
        
        # PnL y Win/Loss (Separamos Ganancia Bruta de Pérdida Bruta)
        if pnl > 0:
            self.wins += 1
            self.gross_profit += pnl
        else:
            self.losses += 1
            self.gross_loss += abs(pnl) # Guardamos valor absoluto para sumar

        # Historial Detallado (Hora, Tipo, Estrategia, Resultado)
        self.trade_history.append({
            'hora': datetime.now().strftime('%H:%M:%S'),
            'tipo': tipo,
            'strat': estrategia,
            'pnl': pnl
        })

    def obtener_reporte(self):
        duration = datetime.now() - self.start_time
        net_pnl = self.gross_profit - self.gross_loss
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        
        # Construcción del Reporte Visual
        reporte = f"""
        {Fore.CYAN}=============================================================
        📊 REPORTE DE CONTROL ESTADÍSTICO (TESTNET)
        ============================================================={Style.RESET_ALL}
        ⏱️  Duración Sesión:   {str(duration).split('.')[0]}
        
        🔢  RESUMEN OPERATIVO:
            • Total Operaciones: {self.total_trades}
            • Tasa de Acierto:   {win_rate:.2f}% ({self.wins} ✅ / {self.losses} ❌)
            • Dirección:         {self.longs} Longs / {self.shorts} Shorts
            
        🧠  DESGLOSE POR MOTOR:
            • Scalping (1m):     {self.scalp_ops} ops
            • Swing (15m):       {self.swing_ops} ops
            
        💰  BALANCE FINANCIERO:
            • Ganancia Bruta:    {Fore.GREEN}+ {self.gross_profit:.2f} USDT{Style.RESET_ALL}
            • Pérdida Bruta:     {Fore.RED}- {self.gross_loss:.2f} USDT{Style.RESET_ALL}
            -------------------------------------
            • PnL NETO:          {Fore.GREEN if net_pnl >= 0 else Fore.RED}{net_pnl:.2f} USDT{Style.RESET_ALL}
            
        📜  DETALLE DE OPERACIONES:
            {'HORA':<10} | {'TIPO':<6} | {'MOTOR':<8} | {'RESULTADO' :<15}
            {'-'*50}
        """
        
        # Agregar filas del historial
        for t in self.trade_history:
            color_pnl = Fore.GREEN if t['pnl'] >= 0 else Fore.RED
            reporte += f"            {t['hora']:<10} | {t['tipo']:<6} | {t['strat']:<8} | {color_pnl}{t['pnl']:>9.2f} USDT{Style.RESET_ALL}\n"
            
        reporte += f"\n{Fore.CYAN}============================================================={Style.RESET_ALL}"
        return reporte

class TradingManager:
    def __init__(self, config, connector):
        self.cfg = config
        self.conn = connector 
        self.step_size = connector.step_size
        self.posicion_abierta = None 
        self.last_closure_time = None
        self.consecutive_losses = 0
        self.last_loss_side = None
        self.dca_level = 0
        self.stats = TradingStats() # Inicializamos el motor de stats
        self._inicializar_csv()
        if self.cfg.MODE in ['TESTNET', 'LIVE']: self._sincronizar_estado_inicial()

    def _sincronizar_estado_inicial(self):
        try:
            pos_data = self.conn.obtener_posicion_abierta()
            if pos_data:
                amt = float(pos_data['positionAmt'])
                entry = float(pos_data['entryPrice'])
                side = 'LONG' if amt > 0 else 'SHORT'
                print(f"{Fore.YELLOW}[MEMORIA] Posición {side} detectada. Restaurando...{Style.RESET_ALL}")
                self.posicion_abierta = {
                    'tipo': side, 'entrada': entry, 'cantidad': abs(amt),
                    'tp': 0.0, 'sl': 0.0, 'motivo': "RECUPERADO", 'strategy': 'RECOVERED',
                    'break_even_activado': False, 'best_price': entry,
                    'sl_order_id': None, 'tp_order_id': None
                }
        except Exception as e: print(f"{Fore.RED}[ERROR MEMORIA] {e}{Style.RESET_ALL}")

    def _inicializar_csv(self):
        if not os.path.exists(self.cfg.TRADES_FILE):
            with open(self.cfg.TRADES_FILE, 'w', newline='') as f:
                csv.writer(f).writerow(['Time', 'Type', 'Entry', 'Qty', 'Strat', 'TP', 'SL', 'Status', 'PnL'])

    def _actualizar_ordenes_proteccion(self, pos):
        if self.cfg.MODE not in ['TESTNET', 'LIVE']: return
        
        if pos.get('sl_order_id'): 
            self.conn.cancelar_orden(pos['sl_order_id'])
            pos['sl_order_id'] = None
        if pos.get('tp_order_id'): 
            self.conn.cancelar_orden(pos['tp_order_id'])
            pos['tp_order_id'] = None

        side_cierre = 'SELL' if pos['tipo'] == 'LONG' else 'BUY'
        pos_side = 'LONG' if pos['tipo'] == 'LONG' else 'SHORT'
        qty = pos['cantidad']
        
        if pos['sl'] > 0:
            res = self.conn.colocar_orden_sl_tp(side_cierre, qty, pos['sl'], pos_side, 'STOP_MARKET')
            if res: 
                pos['sl_order_id'] = res['orderId']
                print(f"{Fore.CYAN}[BINANCE] SL enviado.{Style.RESET_ALL}")
            
        if pos['tp'] > 0:
            res = self.conn.colocar_orden_sl_tp(side_cierre, qty, pos['tp'], pos_side, 'TAKE_PROFIT_MARKET')
            if res: 
                pos['tp_order_id'] = res['orderId']
                print(f"{Fore.CYAN}[BINANCE] TP enviado.{Style.RESET_ALL}")

    def abrir_orden(self, tipo, precio, tp, sl, motivo, estrategia='SCALP', es_dca=False):
        pct_size = self.cfg.SIZE_SWING if estrategia == 'SWING' else self.cfg.SIZE_SCALP
        if es_dca: pct_size = self.cfg.SIZE_SCALP 
        margen = self.cfg.CAPITAL_TRABAJO * pct_size
        qty = utils.calcular_cantidad_ajustada(precio, margen * self.cfg.LEVERAGE, self.step_size)
        
        if qty == 0: return print(f"{Fore.RED}Error: Qty 0{Style.RESET_ALL}")

        if self.cfg.MODE in ['TESTNET', 'LIVE']:
            side = 'BUY' if tipo == 'LONG' else 'SELL'
            pos_side = 'LONG' if tipo == 'LONG' else 'SHORT'
            order = self.conn.colocar_orden_market(side, qty, pos_side)
            if not order: 
                print(f"{Fore.RED}Falló orden de entrada.{Style.RESET_ALL}")
                return

        if self.posicion_abierta:
            pos = self.posicion_abierta
            if pos['strategy'] == 'SWING' and estrategia == 'SCALP': return 
            if pos['tipo'] != tipo: return
            new_qty = pos['cantidad'] + qty
            new_entry = ((pos['entrada']*pos['cantidad']) + (precio*qty)) / new_qty
            pos.update({'entrada': new_entry, 'cantidad': new_qty, 'break_even_activado': False})
            if es_dca: self.dca_level += 1
            self._actualizar_ordenes_proteccion(pos)
        else:
            self.posicion_abierta = {
                'tipo': tipo, 'entrada': precio, 'cantidad': qty, 'tp': tp, 'sl': sl,
                'motivo': motivo, 'strategy': estrategia, 'break_even_activado': False, 
                'best_price': precio, 'sl_order_id': None, 'tp_order_id': None
            }
            self.dca_level = 0
            self._actualizar_ordenes_proteccion(self.posicion_abierta)
            print(f"{Fore.MAGENTA}>>> [{tipo}] {estrategia} OPEN @ {precio:.2f}{Style.RESET_ALL}")

    def verificar_salidas(self, precio):
        if not self.posicion_abierta: return None
        if self.cfg.MODE in ['TESTNET', 'LIVE']:
            if self._verificar_cierre_externo(): return "CERRADO_POR_BINANCE"
        
        pos = self.posicion_abierta
        if pos['strategy'] == 'SCALP' and self.cfg.ENABLE_AUTO_DCA and self.dca_level < self.cfg.MAX_DCA_LEVELS:
            trigger = 1 - self.cfg.DCA_TRIGGER_PCT if pos['tipo'] == 'LONG' else 1 + self.cfg.DCA_TRIGGER_PCT
            if (pos['tipo'] == 'LONG' and precio <= pos['entrada']*trigger) or \
               (pos['tipo'] == 'SHORT' and precio >= pos['entrada']*trigger):
                self.abrir_orden(pos['tipo'], precio, pos['entrada'], pos['sl'], "AUTO_DCA", 'SCALP', True)
                return "DCA EJECUTADO"
        return self._gestionar_riesgo(precio, pos)

    def _verificar_cierre_externo(self):
        pos_real = self.conn.obtener_posicion_abierta()
        if not pos_real:
            print(f"{Fore.GREEN}>>> Cierre externo detectado. Limpiando estado...{Style.RESET_ALL}")
            self.posicion_abierta = None
            return True
        return False

    def _gestionar_riesgo(self, precio, pos):
        strat = pos.get('strategy', 'SCALP')
        be_trigger = self.cfg.SWING_BE if strat == 'SWING' else self.cfg.SCALP_BE_TRIGGER
        trail_dist = self.cfg.SWING_TRAIL if strat == 'SWING' else self.cfg.SCALP_TRAIL_DIST
        changed = False; msg = None
        if pos['entrada'] == 0: return None
        pnl_pct = (precio - pos['entrada'])/pos['entrada'] if pos['tipo']=='LONG' else (pos['entrada'] - precio)/pos['entrada']
        
        if pnl_pct >= be_trigger and not pos['break_even_activado']:
            pos['sl'] = pos['entrada'] * (1.001 if pos['tipo']=='LONG' else 0.999)
            pos['break_even_activado'] = True; changed = True; msg = "B/E ACTIVADO"
            
        trigger_trail = be_trigger * 1.5
        if pnl_pct >= trigger_trail:
            n_sl = precio * (1 - trail_dist) if pos['tipo']=='LONG' else precio * (1 + trail_dist)
            if (pos['tipo']=='LONG' and n_sl > pos['sl']) or (pos['tipo']=='SHORT' and n_sl < pos['sl']):
                pos['sl'] = n_sl; changed = True; msg = "TRAILING UPDATE"
        if changed: self._actualizar_ordenes_proteccion(pos)
        return msg

    def forzar_cierre_scalping(self, precio_actual):
        if self.posicion_abierta and self.posicion_abierta.get('strategy') == 'SCALP':
            print(f"{Fore.YELLOW}[PRIORIDAD] Cerrando Scalping...{Style.RESET_ALL}")
            self._cerrar_orden("SWING_OVERRIDE", precio_actual)
            return True
        return False

    def cerrar_posicion_panico(self, p):
        if self.posicion_abierta: self._cerrar_orden("PANIC", p)

    def _cerrar_orden(self, motivo, precio_salida, orden_ejecutada_en_binance=False):
        pos = self.posicion_abierta
        if self.cfg.MODE in ['TESTNET', 'LIVE']:
            if pos.get('sl_order_id'): self.conn.cancelar_orden(pos['sl_order_id'])
            if pos.get('tp_order_id'): self.conn.cancelar_orden(pos['tp_order_id'])
            if not orden_ejecutada_en_binance and motivo != "CERRADO_POR_BINANCE":
                side = 'SELL' if pos['tipo'] == 'LONG' else 'BUY'
                pos_side = 'LONG' if pos['tipo'] == 'LONG' else 'SHORT'
                self.conn.colocar_orden_market(side, pos['cantidad'], pos_side)

        pnl = (precio_salida - pos['entrada']) * pos['cantidad'] if pos['tipo'] == 'LONG' else (pos['entrada'] - precio_salida) * pos['cantidad']
        
        # --- REGISTRO EN ESTADÍSTICAS ---
        # Aquí conectamos el cierre con el motor de reporte
        estrat = pos.get('strategy', 'SCALP') # Default a scalp si no existe
        self.stats.registrar(pos['tipo'], pnl, estrat)
        
        print(f"{Fore.GREEN}>>> CERRADO {motivo} | PnL: {pnl:.2f}{Style.RESET_ALL}")
        self._registrar_log(pos, precio_salida, pnl, motivo)
        self.posicion_abierta = None

    def _registrar_log(self, pos, exit_price, pnl, motivo): 
        try:
            with open(self.cfg.TRADES_FILE, 'a', newline='') as f:
                csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), pos['tipo'], f"{pos['entrada']:.2f}", pos['cantidad'], pos.get('strategy', 'UNK'), f"{pos['tp']:.2f}", f"{pos['sl']:.2f}", motivo, f"{pnl:.2f}"])
        except: pass

class StrategyEngine:
    def __init__(self, config, connector):
        self.cfg = config
        self.trader = TradingManager(config, connector)
        self.COOLDOWN_SECONDS = 3 
        self.ultimo_precio = 0.0 
        self.gatillo = None 
        self._start_keys()
        
    def _start_keys(self):
        def run():
            try:
                for i in range(1, 10):
                    keyboard.add_hotkey(f'c+{i}', lambda x=i: self._manual('LONG', x))
                    keyboard.add_hotkey(f'v+{i}', lambda x=i: self._manual('SHORT', x))
                keyboard.add_hotkey('z+x+0', lambda: self.trader.cerrar_posicion_panico(self.ultimo_precio))
                keyboard.wait() 
            except: pass
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _manual(self, tipo, multi):
        p = self.ultimo_precio
        if p == 0: return
        tp = p * 1.01 if tipo=='LONG' else p * 0.99
        sl = p * 0.995 if tipo=='LONG' else p * 1.005
        self.trader.abrir_orden(tipo, p, tp, sl, f"MANUAL x{multi}", 'SCALP', False)

    def analizar_ind_vol(self, df):
        if len(df) < 2: return 0, {}
        curr, prev = df.iloc[-1], df.iloc[-2]
        score = 0
        try:
            score += 45 if ((curr['OBV'] > prev['OBV']) == (curr['close'] > prev['close'])) else 0
            score += 35 if curr['close'] > curr['VWAP'] else 0
            score += 20 if curr['ADI'] > prev['ADI'] else 0
        except: pass
        return score, {'OBV': score}

    def ejecutar_estrategia(self, df_scalp, df_swing, roll_min, roll_max, precio):
        last_s = df_scalp.iloc[-1]
        last_w = df_swing.iloc[-1]
        self.ultimo_precio = precio
        res = self.trader.verificar_salidas(precio)
        if res: 
            self.gatillo = None
            return f"Gestionando: {res}"

        if self.trader.last_closure_time and (datetime.now() - self.trader.last_closure_time).total_seconds() < self.COOLDOWN_SECONDS:
            return "Cooldown..."

        if 'RSI' not in last_w or pd.isna(last_w['RSI']): return "Esperando datos Swing..."
            
        if last_w['RSI'] < self.cfg.SWING_RSI_OS:
             if not self.trader.posicion_abierta or self.trader.posicion_abierta.get('strategy') == 'SCALP':
                 self.trader.forzar_cierre_scalping(precio)
                 tp = roll_max 
                 sl = precio * (1 - self.cfg.SWING_SL)
                 self.trader.abrir_orden('LONG', precio, tp, sl, "SWING SIGNAL", 'SWING')
                 return "ENTRADA SWING LONG"

        elif last_w['RSI'] > self.cfg.SWING_RSI_OB:
             if not self.trader.posicion_abierta or self.trader.posicion_abierta.get('strategy') == 'SCALP':
                 self.trader.forzar_cierre_scalping(precio)
                 tp = roll_min
                 sl = precio * (1 + self.cfg.SWING_SL)
                 self.trader.abrir_orden('SHORT', precio, tp, sl, "SWING SIGNAL", 'SWING')
                 return "ENTRADA SWING SHORT"

        if self.trader.posicion_abierta and self.trader.posicion_abierta.get('strategy') == 'SWING': return "MONITOREO SWING..."

        if self.gatillo:
            g = self.gatillo
            g['ticks'] -= 1
            if g['ticks'] <= 0: self.gatillo = None; return "Gatillo Exp."
            verde = last_s['close'] > last_s['open']
            if g['tipo']=='LONG' and verde and precio > g['price']:
                tp = roll_max * 0.999; sl = precio * (1-self.cfg.SCALP_SL_PCT)
                self.trader.abrir_orden('LONG', precio, tp, sl, "SCALP", 'SCALP')
                self.gatillo = None; return "DISPARO SCALP LONG"
            elif g['tipo']=='SHORT' and not verde and precio < g['price']:
                tp = roll_min * 1.001; sl = precio * (1+self.cfg.SCALP_SL_PCT)
                self.trader.abrir_orden('SHORT', precio, tp, sl, "SCALP", 'SCALP')
                self.gatillo = None; return "DISPARO SCALP SHORT"
            return "Gatillo Armado..."

        vol_score, _ = self.analizar_ind_vol(df_scalp)
        if not self.trader.posicion_abierta:
            ma99 = last_s.get('MA99')
            if ma99 is None or pd.isna(ma99): return "Cargando MA99..."
            trend_ok_long = precio > ma99
            trend_ok_short = precio < ma99
            if last_s['RSI'] < self.cfg.SCALP_RSI_OS:
                if self.cfg.ENABLE_TREND_FILTER and not trend_ok_long: return "Filtro MA99: LONG Bloqueado"
                if vol_score >= self.cfg.VOL_SCORE_THRESHOLD:
                    self.gatillo = {'tipo': 'LONG', 'price': precio, 'ticks': self.cfg.TRIGGER_PATIENCE}
                    return "SEÑAL SCALP LONG"
            if last_s['RSI'] > self.cfg.SCALP_RSI_OB:
                if self.cfg.ENABLE_TREND_FILTER and not trend_ok_short: return "Filtro MA99: SHORT Bloqueado"
                if vol_score >= self.cfg.VOL_SCORE_THRESHOLD:
                    self.gatillo = {'tipo': 'SHORT', 'price': precio, 'ticks': self.cfg.TRIGGER_PATIENCE}
                    return "SEÑAL SCALP SHORT"
        return "Escaneo Dual..."