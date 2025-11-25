import time
import threading
from sqlalchemy.orm import Session
from app.copy_trader import CopyTrader
import app.config as config

class MonitoringService:
    def __init__(self, db: Session):
        self.db = db
        self.copy_trader = CopyTrader(db)
        self.is_running = False
        self.thread = None
    
    def start(self):
        """Start the monitoring service in a background thread"""
        if self.is_running:
            print("Monitoring service is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Monitoring service started")
    
    def stop(self):
        """Stop the monitoring service"""
        self.is_running = False
        if self.thread:
            self.thread.join()
        print("Monitoring service stopped")
    
    def _run_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                self.copy_trader.process_leader_trades()
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
            
            # Wait for next check
            time.sleep(config.CHECK_INTERVAL)