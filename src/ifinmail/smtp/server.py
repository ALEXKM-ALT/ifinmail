import asyncio
import logging

import aiosmtpd.controller

from ifinmail.smtp.handler import SMTPHandler

logger = logging.getLogger("ifinmail.smtp")


def start_smtp_server(host: str = "0.0.0.0", port: int = 25) -> None:
    handler = SMTPHandler()
    controller = aiosmtpd.controller.Controller(
        handler,
        hostname=host,
        port=port,
    )
    controller.start()
    logger.info("SMTP receiver listening on %s:%s", host, port)
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
