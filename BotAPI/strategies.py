# strategies.py
import csv
import os
import time
import keyboard
import threading
from datetime import datetime
from colorama import Fore, Style
import utils

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
        self._inicializar_csv()

    def _inicializar_csv(self):
        if not os.path.exists(self.cfg.TRADES_FILE):
            with open(self.cfg.TRADES_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time', 'Type', 'Entry', 'Qty', 'Strat', 'TP', 'SL', 'Status', 'PnL'])

    def _actualizar_ordenes_proteccion(self, pos):
        if self.cfg.MODE not in ['TESTNET', 'LIVE']: return
        
        if pos.get('sl_order_id'): self.conn.cancelar_orden(pos['sl_order_id']); pos['sl_order_id']=None
        if pos.get('tp_order_id'): self.conn.cancelar_orden(pos['tp_order_id']); pos['tp_order_id']=None

        side_cierre = 'SELL' if pos['tipo'] == 'LONG' else 'BUY'
        pos_side = 'LONG' if pos['tipo'] == 'LONG' else 'SHORT'
        qty = pos['cantidad']
        
        if pos['sl'] > 0:
            res = self.conn.colocar_orden_sl_tp(side_cierre, qty, round(pos['sl'], 2), pos_side, 'STOP_MARKET')
            if res: pos['sl_order_id'] = res['orderId']
            
        if pos['tp'] > 0:
            res = self.conn.colocar_orden_sl_tp(side_cierre, qty, round(pos['tp'], 2), pos_side, 'TAKE_PROFIT_MARKET')
            if res: pos['tp_order_id'] = res['orderId']

    def forzar_cierre_scalping(self, precio_actual):
        if self.posicion_abierta and self.posicion_abierta.get('strategy') == 'SCALP':
            print(f"{Fore.YELLOW}[PRIORIDAD] Cerrando Scalping para entrada SWING...{Style.RESET_ALL}")
            self._cerrar_orden("SWING_OVERRIDE", precio_actual)
            return True
        return False

    def abrir_orden(self, tipo, precio, tp, sl, motivo, estrategia='SCALP', es_dca=False):
        pct_size = self.cfg.SIZE_SWING if estrategia == 'SWING' else self.cfg.SIZE_SCALP
        if es_dca: pct_size = self.cfg.SIZE_SCALP 
        margen = self.cfg.CAPITAL_TRABAJO * pct_size
        qty = utils.calcular_cantidad_ajustada(precio, margen * self.cfg.LEVERAGE, self.step_size)
        
        if qty == 0: return print(f"{Fore.RED}Error: Qty 0{Style.RESET_ALL}")

        if self.cfg.MODE in ['TESTNET', 'LIVE']:
            side = 'BUY' if tipo == 'LONG' else 'SELL'
            pos_side = 'LONG' if tipo == 'LONG' else 'SHORT'
            if not self.conn.colocar_orden_market(side, qty, pos_side): return

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
        pos = self.posicion_abierta
        
        if pos['strategy'] == 'SCALP' and self.cfg.ENABLE_AUTO_DCA and self.dca_level < self.cfg.MAX_DCA_LEVELS:
            trigger = 1 - self.cfg.DCA_TRIGGER_PCT if pos['tipo'] == 'LONG' else 1 + self.cfg.DCA_TRIGGER_PCT
            if (pos['tipo'] == 'LONG' and precio <= pos['entrada']*trigger) or \
               (pos['tipo'] == 'SHORT' and precio >= pos['entrada']*trigger):
                self.abrir_orden(pos['tipo'], precio, pos['entrada'], pos['sl'], "AUTO_DCA", 'SCALP', True)
                return "DCA EJECUTADO"

        return self._gestionar_riesgo(precio, pos)

    def _gestionar_riesgo(self, precio, pos):
        strat = pos.get('strategy', 'SCALP')
        be_trigger = self.cfg.SWING_BE if strat == 'SWING' else self.cfg.SCALP_BE_TRIGGER
        trail_dist = self.cfg.SWING_TRAIL if strat == 'SWING' else self.cfg.SCALP_TRAIL_DIST
        
        changed = False; msg = None
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

    def cerrar_posicion_panico(self, p):
        if self.posicion_abierta: self._cerrar_orden("PANIC", p)

    def _cerrar_orden(self, motivo, precio_salida, orden_ejecutada_en_binance=False):
        pos = self.posicion_abierta
        if self.cfg.MODE in ['TESTNET', 'LIVE']:
            if pos.get('sl_order_id'): self.conn.cancelar_orden(pos['sl_order_id'])
            if pos.get('tp_order_id'): self.conn.cancelar_orden(pos['tp_order_id'])
            
            if not orden_ejecutada_en_binance:
                side = 'SELL' if pos['tipo'] == 'LONG' else 'BUY'
                pos_side = 'LONG' if pos['tipo'] == 'LONG' else 'SHORT'
                self.conn.colocar_orden_market(side, pos['cantidad'], pos_side)

        pnl = (precio_salida - pos['entrada']) * pos['cantidad'] if pos['tipo'] == 'LONG' else (pos['entrada'] - precio_salida) * pos['cantidad']
        if pnl < 0 and pos.get('strategy') == 'SCALP': 
            self.consecutive_losses += 1
            self.last_loss_side = pos['tipo']
        else: 
            self.consecutive_losses = 0
            
        self.posicion_abierta = None
        print(f"{Fore.GREEN}>>> CERRADO {motivo} | PnL: {pnl:.2f}{Style.RESET_ALL}")
        self._registrar_log(pos['tipo'], pos['entrada'], pos['tp'], pos['sl'], motivo, pnl, pos['cantidad'], pos.get('strategy'))

    def _registrar_log(self, *args): pass

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
            for i in range(1, 10):
                keyboard.add_hotkey(f'c+{i}', lambda x=i: self._manual('LONG', x))
                keyboard.add_hotkey(f'v+{i}', lambda x=i: self._manual('SHORT', x))
            keyboard.add_hotkey('z+x+0', lambda: self.trader.cerrar_posicion_panico(self.ultimo_precio))
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _manual(self, tipo, multi):
        p = self.ultimo_precio
        if p == 0: return
        tp = p * 1.01 if tipo=='LONG' else p * 0.99
        sl = p * 0.995 if tipo=='LONG' else 1.005
        self.trader.abrir_orden(tipo, p, tp, sl, f"MANUAL x{multi}", 'SCALP', multi)

    def analizar_ind_vol(self, df):
        if len(df) < 2: return 0, {}
        curr, prev = df.iloc[-1], df.iloc[-2]
        score = 0
        score += 45 if ((curr['OBV'] > prev['OBV']) == (curr['close'] > prev['close'])) else 0
        score += 35 if curr['close'] > curr['VWAP'] else 0
        score += 20 if curr['ADI'] > prev['ADI'] else 0
        return score, {'OBV': score}

    def ejecutar_estrategia(self, df_scalp, df_swing, roll_min, roll_max, precio):
        last_s = df_scalp.iloc[-1]
        last_w = df_swing.iloc[-1]
        self.ultimo_precio = precio
        
        res = self.trader.verificar_salidas(precio)
        if res: 
            self.gatillo = None
            return f"Gestionando: {res}"

        if self.trader.last_closure_time:
            if (datetime.now() - self.trader.last_closure_time).total_seconds() < self.COOLDOWN_SECONDS:
                return "Cooldown..."

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

        if self.trader.posicion_abierta and self.trader.posicion_abierta.get('strategy') == 'SWING':
            return "MONITOREO SWING..."

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
            ma99 = last_s['MA99']
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