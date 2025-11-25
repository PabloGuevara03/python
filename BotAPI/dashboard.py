# dashboard.py
from colorama import Fore, Back, Style
from datetime import datetime 
import os
import sys

_first_run = True

def mostrar_panel(df_scalp, df_swing, vol_score, funcion_activa, modo, trader_state):
    global _first_run
    
    if _first_run: 
        os.system('cls' if os.name == 'nt' else 'clear')
        _first_run = False
    
    print("\033[H", end="")
    
    # --- PREPARACIÓN DE DATOS ---
    last_s = df_scalp.iloc[-1]
    last_w = df_swing.iloc[-1]
    ahora = datetime.now().strftime('%H:%M:%S')
    
    # Tendencias
    trend_s = f"{Fore.GREEN}ALCISTA" if last_s['MA7'] > last_s['MA25'] else f"{Fore.RED}BAJISTA"
    trend_w = f"{Fore.GREEN}ALCISTA" if last_w['MA7'] > last_w['MA25'] else f"{Fore.RED}BAJISTA"
    
    # Colores RSI
    def color_rsi(val, is_scalp=True):
        if is_scalp:
            if val > 75: return Fore.RED 
            if val < 25: return Fore.GREEN
        else:
            if val > 70: return Fore.RED
            if val < 30: return Fore.GREEN
        return Fore.WHITE

    c_rsi_s = color_rsi(last_s['RSI'], True)
    c_rsi_w = color_rsi(last_w['RSI'], False)

    # --- RENDERIZADO ---
    print(f"{Back.BLUE}{Fore.WHITE}=== SENTINEL PRO DUAL ({modo}) - {ahora} ==={Style.RESET_ALL}".center(80))
    print(f" PRECIO ACTUAL: {Fore.YELLOW}{Style.BRIGHT}{last_s['close']:.2f}{Style.RESET_ALL}".center(80))
    print("-" * 78)

    # Encabezados
    print(f"{Fore.CYAN}{'   ⚡ MOTOR SCALPING (1m)':<38} | {Fore.MAGENTA}{'   🌊 MOTOR SWING (15m)':<38}{Style.RESET_ALL}")
    print("-" * 78)

    # Métricas
    print(f" Tendencia: {trend_s:<26}{Style.RESET_ALL} |  Tendencia: {trend_w:<26}{Style.RESET_ALL}")
    
    rsi_s_str = f"{c_rsi_s}{last_s['RSI']:.1f}{Style.RESET_ALL}"
    rsi_w_str = f"{c_rsi_w}{last_w['RSI']:.1f}{Style.RESET_ALL}"
    print(f" RSI:       {rsi_s_str:<35} |  RSI:       {rsi_w_str:<35}")

    stoch_s = f"{last_s['StochRSI_k']:.2f}"
    stoch_w = f"{last_w['StochRSI_k']:.2f}"
    print(f" Stoch K:   {stoch_s:<26} |  Stoch K:   {stoch_w:<26}")

    ma99_s = f"{last_s['MA99']:.1f}"
    ma99_w = f"{last_w['MA99']:.1f}"
    print(f" MA99:      {ma99_s:<26} |  MA99:      {ma99_w:<26}")

    print("-" * 78)

    # --- SECCIÓN INFERIOR ---
    c_vol = Fore.GREEN if vol_score > 20 else Fore.RED
    print(f" 📊 Volumetría (Scalp): {c_vol}{vol_score}%{Style.RESET_ALL}")
    
    estado_g = "ESPERANDO"
    if "GATILLO" in str(funcion_activa): estado_g = f"{Fore.YELLOW}ARMADO{Style.RESET_ALL}"
    elif "SWING" in str(funcion_activa): estado_g = f"{Fore.MAGENTA}EJECUCIÓN SWING{Style.RESET_ALL}"
    elif "CERRADO" in str(funcion_activa): estado_g = f"{Fore.GREEN}GESTIONANDO CIERRE{Style.RESET_ALL}"
    
    print(f" ⚙️  STATUS: {estado_g}")
    print(f" 💬 MSG:    {funcion_activa}")
    print("=" * 78)
    
    if trader_state:
        t = trader_state
        tipo = t['tipo']
        pnl_u = (last_s['close'] - t['entrada']) * t['cantidad']
        if tipo == 'SHORT': pnl_u *= -1
        
        bg_pnl = Back.GREEN if pnl_u >= 0 else Back.RED
        
        print(f"{bg_pnl}{Fore.WHITE}  POSICIÓN ACTIVA: {tipo} ({t.get('strategy', 'UNK')})  {Style.RESET_ALL}")
        print(f"  Entrada: {t['entrada']:.2f}  |  Cantidad: {t['cantidad']}")
        print(f"  TP:      {t['tp']:.2f}     |  SL:       {t['sl']:.2f}")
        print(f"  PnL:     {Fore.WHITE}{Style.BRIGHT}{pnl_u:.2f} USD{Style.RESET_ALL}")
    else:
        # CORRECCIÓN AQUÍ: Se cambió Fore.DIM por Style.DIM
        print(f"{Style.DIM}\n       [ NO HAY POSICIONES ABIERTAS ]\n{Style.RESET_ALL}")

    print("=" * 78)
    print("\033[J", end="")
    sys.stdout.flush()