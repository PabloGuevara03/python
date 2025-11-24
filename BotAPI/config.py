# config.py
import os

class Config:
    # ==========================================
    # 1. MODO Y CREDENCIALES
    # ==========================================
    MODE = 'TESTNET' 
    
    API_KEY =  "7taoqalyG9M2AjDizAPphthbOYN18pIYZpy3eOltVM3OsisbvJBXZjySpn8WFeDJ"   
    API_SECRET =  "eJpFCSoWVS59QgKTkhQpmvQnRHLGy5MCQPZ4pHZ02jMOWGbfeLlBNbH3Afb6EAsR"
    
    # ==========================================
    # 2. MERCADO Y TIEMPOS
    # ==========================================
    SYMBOL = 'BTC/USDT'  
    USE_REAL_DATA_FOR_SIM = False 
    
    # Timeframes para Estrategia Dual
    TF_SCALP = '1m'
    TF_SWING = '15m'
    
    # Retro-compatibilidad
    TIMEFRAME_LIVE = TF_SCALP 
    TIMEFRAME_INIT = '5m'
    
    # ==========================================
    # 3. GESTIÓN DE CAPITAL
    # ==========================================
    CAPITAL_TRABAJO = 1000     
    LEVERAGE = 10
    
    SIZE_SCALP = 0.02  # 2% Capital
    SIZE_SWING = 0.10  # 10% Capital
    
    # ==========================================
    # 4. ESTRATEGIA SCALPING (1m)
    # ==========================================
    SCALP_RSI_PERIOD = 7             
    SCALP_RSI_OB = 75        
    SCALP_RSI_OS = 25          
    SCALP_VOL_THRESHOLD = 20   
    
    # Riesgo Scalping
    SCALP_SL_PCT = 0.004       # 0.4% Stop Loss Inicial
    SCALP_BE_TRIGGER = 0.002   # 0.2% Trigger Break Even
    SCALP_TRAIL_DIST = 0.0015  # 0.15% Distancia Trailing
    
    # ==========================================
    # 5. ESTRATEGIA SWING (15m)
    # ==========================================
    SWING_RSI_PERIOD = 14
    SWING_RSI_OB = 70
    SWING_RSI_OS = 30
    
    SWING_SL = 0.02        
    SWING_TP = 0.06        
    SWING_BE = 0.01        
    SWING_TRAIL = 0.005    
    
    # ==========================================
    # 6. AUTO-DCA Y FILTROS
    # ==========================================
    ENABLE_AUTO_DCA = True     
    DCA_TRIGGER_PCT = 0.008    
    DCA_MULTIPLIER = 1.5       
    MAX_DCA_LEVELS = 3         
    
    ENABLE_TREND_FILTER = True
    TRIGGER_PATIENCE = 5
    STOCH_K_OVERSOLD = 0.2
    STOCH_K_OVERBOUGHT = 0.8
    VOL_SCORE_THRESHOLD = 20
    
    SR_WINDOW = 20 

    # ==========================================
    # 7. ARCHIVOS
    # ==========================================
    LOG_FILE = 'system_log.txt'
    TRADES_FILE = 'reporte_ordenes.csv'