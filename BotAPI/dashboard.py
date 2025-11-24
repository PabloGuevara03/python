# dashboard.py
from colorama import Fore, Back, Style
from datetime import datetime 
import os
import sys

_first_run = True

def mostrar_panel(df, vol_score, vol_details, funcion_activa, modo, trader_state):
    global _first_run
    es_cierre = "Cierre" in str(funcion_activa)
    if _first_run or es_cierre: os.system('cls' if os.name == 'nt' else 'clear'); _first_run = False
    
    print("\033[H", end="")
    last = df.iloc[-1]
    ahora = datetime.now().strftime('%H:%M:%S') 
    
    print(f"{Back.BLUE}{Fore.WHITE}=== SENTINEL PRO DUAL ({modo}) - {ahora} ==={Style.RESET_ALL}")
    
    ma7, ma25, ma99 = last['MA7'], last['MA25'], last['MA99']
    tendencia = f"{Fore.GREEN}ALCISTA" if ma7 > ma25 else f"{Fore.RED}BAJISTA"

    print(f" PRECIO: {Fore.WHITE}{Style.BRIGHT}{last['close']:.2f}{Style.RESET_ALL} | TENDENCIA: {tendencia}")
    print("-" * 60)
    print(f" RSI(1m): {last['RSI']:.1f} | Stoch: {last['StochRSI_k']:.2f} | MA99: {ma99:.1f}")
    print("-" * 60)
    
    color_vol = Fore.GREEN if vol_score > 20 else Fore.RED
    print(f" Vol Score: {color_vol}{vol_score}%{Style.RESET_ALL}")
    
    estado_g = "ESPERANDO"
    if "GATILLO" in str(funcion_activa): estado_g = f"{Fore.YELLOW}ARMADO{Style.RESET_ALL}"
    if "SWING" in str(funcion_activa): estado_g = f"{Fore.MAGENTA}SWING SIGNAL{Style.RESET_ALL}"
    
    print(f" STATUS: {estado_g} | MSG: {funcion_activa}")
    print("=" * 60)
    
    if trader_state:
        tipo = trader_state['tipo']
        strat = trader_state.get('strategy', 'MANUAL')
        pnl_sim = (last['close'] - trader_state['entrada']) * trader_state['cantidad']
        if tipo == 'SHORT': pnl_sim *= -1
        
        bg = Back.GREEN if tipo == 'LONG' else Back.RED
        print(f"{bg}{Fore.WHITE} POS: {tipo} ({strat}){Style.RESET_ALL} | PnL: {pnl_sim:.2f}")
        print(f" Entry: {trader_state['entrada']:.2f} | SL: {trader_state['sl']:.2f}")
    else:
        print(" " * 60)
        print(" " * 60)

    print("=" * 60)
    print("\033[J", end="")
    sys.stdout.flush()