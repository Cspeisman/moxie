import shlex
import asyncio
from aiocore import EventService


class RunService(EventService):
    identifier = "moxie.cores.run.RunService"

    @asyncio.coroutine
    def _getc(self, job):
        try:
            container = yield from self.containers.get(job.name)
            return container
        except ValueError:
            return None

    @asyncio.coroutine
    def _bringup(self, job):
        container = yield from self._getc(job)
        cmd = shlex.split(job.command)

        if container:
            if container._container.get(
                    "State", {}).get("Running", False) is True:
                raise ValueError("Container {} still running!".format(job.name))

            cfg = container._container
            if cfg['Args'] != cmd or cfg['Image'] != job.image:
                yield from container.delete()
                container = None

        if container is None:
            c = yield from self._create(job)
            if c is None:
                yield from self.logger.log(
                    "run", "Uch, container {} couldn't be created.".format(
                        job['name']
                    ))
                return
            container = c

        return container

    @asyncio.coroutine
    def _create(self, job):
        container = yield from self._getc(job)

        if container is not None:
            raise ValueError("Error: Told to create container that exists.")

        cmd = shlex.split(job.command)

        jobenvs = yield from self.database.env.get(job.env_id)
        volumes = yield from self.database.volume.get(job.volumes_id)

        env = ["{key}={value}".format(**x) for x in jobenvs]
        volumes = {x.host: x.container for x in volumes}

        yield from self.logger.log("run", "Pulling: %s" % (job.image))
        try:
            yield from self.containers.pull(job.image)
        except ValueError:
            yield from self.logger.log("run", "Pull failure for %s" % (
                job.image
            ))
            return None

        yield from self.logger.log("run", "Creating a new container")
        try:
            container = yield from self.containers.create(
                {"Cmd": cmd,
                 "Image": job.image,
                 "Env": env,
                 "AttachStdin": True,
                 "AttachStdout": True,
                 "AttachStderr": True,
                 "ExposedPorts": [],
                 "Volumes": volumes,
                 "Tty": True,
                 "OpenStdin": False,
                 "StdinOnce": False},
                name=job.name)
            yield from self.logger.log("run", "Got a container: %s" % (
                container._id
            ))
        except ValueError as e:
            yield from self.logger.log(
                "run", "Creation failure for {}: {}".format(job['name'], e))
            return

        return container

    @asyncio.coroutine
    def run(self, job):
        return (yield from self.send({
            "type": "run",
            "job": job
        }))

    @asyncio.coroutine
    def handle(self, message):
        type_ = message.pop("type")
        return (yield from {"run": self.handle_job}[type_](**message))

    @asyncio.coroutine
    def handle_job(self, job):
        self.containers = EventService.resolve(
            "moxie.cores.container.ContainerService")
        self.database = EventService.resolve(
            "moxie.cores.database.DatabaseService")
        self.logger = EventService.resolve("moxie.cores.log.LogService")

        try:
            good = yield from self.database.job.take(job.name)
        except ValueError:
            yield from self.logger.log("run", "Job already active. Bailing")
            return

        yield from self.logger.log("run", "Running Job: `%s`" % (job.name))
        yield from self._bringup(job)
