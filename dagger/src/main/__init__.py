"""Dagger CI Pipeline for BoundaryLayer
"""

import dagger
import anyio
from dagger import dag, function, object_type, Doc, DefaultPath
from typing import Annotated

# uncomment to enable debug logging:
# import logging
# from dagger.log import configure_logging
# configure_logging(logging.DEBUG)

@object_type
class BoundaryLayer:

    dir: Annotated[dagger.Directory, Doc("Directory containing source code"), DefaultPath("/")]
    env: Annotated[str, Doc("Environment where Dagger is running")] = "local"
    version: Annotated[str, Doc("Python version for base image")] = "3.12"

    @function
    def base(
        self,
    ) -> dagger.Container:
        """Return base python container"""
        return (
            dag
            .container()
            .from_(f"python:{self.version}")
            .with_directory("/src", self.dir)
            .with_workdir("/src")
            .with_mounted_cache(
                 f"/root/.cache/pip",
                 dag.cache_volume(f"boundry-layer-python-{self.version}")
            )
            .with_exec(["sh", "-c", "python -m pip install --upgrade pip"])
            .with_exec(["sh", "-c", "pip install tox==3.27.1 flake8"])
        )

    @function
    def lint(self) -> dagger.Container:
        """Run flake8 linter"""
        return (
            self
            .base()
            # stop the build if there are Python syntax errors or undefined names
            .with_exec(["sh", "-c", "flake8 boundary_layer boundary_layer_default_plugin bin test --count --select=E9,F63,F7,F82 --show-source --statistics"])
            # exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
            .with_exec(["sh", "-c", "flake8 boundary_layer boundary_layer_default_plugin bin test --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics"])
        )

    @function
    def test(self) -> dagger.Container:
        """Run tests with tox"""
        # py`echo ${{ matrix.python-version }} | tr -d '.'`  yields py36, py37, etc. which is what tox needs
        return (
            self.
            base()
            .with_exec(["echo", f"tox --recreate -e py`echo {self.version} | tr -d '.'` test"])
        )

    @function
    async def all(self) -> str:
        """Run end to end CI pipline for a specific version"""
        output = [""]*3

        async def run(coro, index):
            output[index] = await coro

        async with anyio.create_task_group() as tg:
            tg.start_soon(run, self.base().with_exec(["python", "--version"]).stdout(), 0)
            tg.start_soon(run, self.lint().stdout(), 1)
            tg.start_soon(run, self.test().stdout(), 2)

        return "\n".join(output)

    @function
    async def ci(self) -> str:
        """Run end to end CI pipeline (using concurrency)."""
        python_versions = ["3.7", "3.8", "3.9"]
        output = []

        async def run(coro):
            output.append(await coro)

        async with anyio.create_task_group() as tg:
            for version in python_versions:
                bl = BoundaryLayer(dir=self.dir, env=self.env, version=version)
                tg.start_soon(run, bl.all())

        return "\n".join(output)
