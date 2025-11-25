# main.py
import time
import logging
import traceback
from colorama import init, Fore
from config import Config
from connectors import BinanceClient, MockClient
from indicators import MarketAnalyzer
from strategies import StrategyEngine
import dashboard

init(autoreset=True)

def main():
    cfg = Config()
    logging.basicConfig(filename=cfg.LOG_FILE, level=logging.INFO)
    print(f"{Fore.CYAN}Iniciando SENTINEL PRO (Modo: {cfg.MODE})...{Fore.RESET}")
    
    if cfg.MODE == 'SIMULATION': 
        client = MockClient(cfg)
    else: 
        client = BinanceClient(cfg)
        
    client.inicializar()
    
    strategy = StrategyEngine(cfg, client)
    print("Sincronizando Timeframes (1m + 15m)...")
    time.sleep(2)

    try:
        while True:
            time.sleep(3) 

            df_scalp = client.obtener_velas(cfg.TF_SCALP)
            df_swing = client.obtener_velas(cfg.TF_SWING)
            
            if df_scalp.empty or df_swing.empty: 
                print(f"{Fore.YELLOW}Esperando datos de mercado...{Fore.RESET}")
                continue

            precio_real = client.obtener_precio_real()
            
            if precio_real:
                df_scalp.iloc[-1, df_scalp.columns.get_loc('close')] = precio_real
                df_scalp.iloc[-1, df_scalp.columns.get_loc('high')] = max(df_scalp.iloc[-1]['high'], precio_real)
                df_scalp.iloc[-1, df_scalp.columns.get_loc('low')] = min(df_scalp.iloc[-1]['low'], precio_real)
                df_swing.iloc[-1, df_swing.columns.get_loc('close')] = precio_real

            ana_scalp = MarketAnalyzer(df_scalp)
            df_s_calc = ana_scalp.calcular_todo(rsi_period=cfg.SCALP_RSI_PERIOD)
            roll_min, roll_max = ana_scalp.obtener_extremos_locales()
            
            ana_swing = MarketAnalyzer(df_swing)
            df_w_calc = ana_swing.calcular_todo(rsi_period=cfg.SWING_RSI_PERIOD)

            log_accion = strategy.ejecutar_estrategia(df_s_calc, df_w_calc, roll_min, roll_max, precio_real)
            
            funcion_activa = log_accion if log_accion else "ESPERA / MONITOREO"
            v_score, _ = strategy.analizar_ind_vol(df_s_calc)
            
            dashboard.mostrar_panel(
                df_s_calc, 
                df_w_calc, # Enviamos ambos DFs al dashboard
                v_score, 
                funcion_activa, 
                cfg.MODE, 
                strategy.trader.posicion_abierta
            )

    except KeyboardInterrupt:
        # --- AQUÍ SE GENERA EL REPORTE FINAL ---
        print("\n\n")
        print(strategy.trader.stats.obtener_reporte())
        print("\nDeteniendo sistema...")
        
    except Exception as e:
        logging.error(traceback.format_exc())
        print(f"\nERROR: {e}")
        time.sleep(5)

if __name__ == "__main__":
    main()