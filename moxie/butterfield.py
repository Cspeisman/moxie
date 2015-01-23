import os
import asyncio
from butterfield.utils import at_bot
from aiocore import Service

WEB_ROOT = os.environ.get("MOXIE_WEB_URL", "http://localhost:8888")

@asyncio.coroutine
@at_bot
def run(bot, message: "message"):
    runner = Service.resolve("moxie.cores.run.RunService")

    text = message.get("text", "")
    if text == "":
        yield from bot.post(message['channel'], "Invalid request")

    cmd, arg = text.split(" ", 1)
    if cmd == "run":
        job = arg
        yield from bot.post(
            message['channel'], "Doing bringup of {}".format(job))
        try:
            yield from runner.run(job)
        except ValueError as e:
            yield from bot.post(
                message['channel'],
                "Gah, {job} failed - {e}".format(e=e, job=job)
            )
            return

        yield from bot.post(message['channel'],
            "Job {job} online - {webroot}/container/{job}/".format(
                webroot=WEB_ROOT, job=job))
