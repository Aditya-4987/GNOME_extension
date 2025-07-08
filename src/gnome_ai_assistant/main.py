#!/usr/bin/env python3
"""
GNOME AI Assistant - Service Entry Point

This module provides the main entry point for the AI assistant service.
The service runs as a systemd user service and provides AI functionality
through Unix domain sockets.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import structlog

from .core.service import AssistantService
from .utils.logger import setup_logging


class ServiceManager:
    """Manages the lifecycle of the AI assistant service."""
    
    def __init__(self) -> None:
        self.service: Optional[AssistantService] = None
        self.shutdown_event = asyncio.Event()
        
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum: int) -> None:
            logging.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown_event.set()
            
        # Handle SIGTERM and SIGINT for graceful shutdown
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))
        
    async def start(self) -> None:
        """Start the AI assistant service."""
        logger = structlog.get_logger()
        
        try:
            # Set up signal handlers
            self._setup_signal_handlers()
            
            # Initialize and start the service
            self.service = AssistantService()
            await self.service.initialize()
            
            logger.info("GNOME AI Assistant service starting...")
            
            # Start the service in the background
            service_task = asyncio.create_task(self.service.start())
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            logger.info("Shutdown signal received, stopping service...")
            
            # Gracefully stop the service
            if self.service:
                await self.service.stop()
                
            # Cancel the service task
            service_task.cancel()
            try:
                await service_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Service startup failed: {e}")
            sys.exit(1)
        finally:
            logger.info("GNOME AI Assistant service stopped")


def main() -> None:
    """Main entry point for the service."""
    # Set up logging
    setup_logging()
    
    # Create and run the service manager
    manager = ServiceManager()
    
    try:
        asyncio.run(manager.start())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
