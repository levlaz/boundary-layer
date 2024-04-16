"""Dagger CI Pipeline for BoundaryLayer
"""

import dagger
from dagger import dag, function, object_type, Doc
from typing import Annotated


@object_type
class BoundaryLayer:

    dir: Annotated[dagger.Directory, Doc("Directory containing source code")]
    version: Annotated[str, Doc("Python version for base image")] = "latest"

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
                 "/root/.cache/pip", 
                 dag.cache_volume(f"boundry-layer-python-{self.version}")
            )
            .with_exec(["sh", "-c", "python -m pip install --upgrade pip"])
            .with_exec(["sh", "-c", "pip install tox==3.27.1 flake8"])
            .with_exec(["sh", "-c", "flake8 boundary_layer boundary_layer_default_plugin bin test --count --select=E9,F63,F7,F82 --show-source --statistics"])
        )

    @function
    async def lint(self) -> str:
        """Run flake8 linter"""
        return await (
            self
            .base()
            # stop the build if there are Python syntax errors or undefined names
            .with_exec(["sh", "-c", "flake8 boundary_layer boundary_layer_default_plugin bin test --count --select=E9,F63,F7,F82 --show-source --statistics"])
            # exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
            .with_exec(["sh", "-c", "flake8 boundary_layer boundary_layer_default_plugin bin test --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics"])
            .stdout()
        )
    
    @function
    async def ci(self) -> str:
        """Run end to end CI pipeline"""
        output = ""
        python_versions = ["3.7", "3.8", "3.9"]

        for version in python_versions:
            self.version = version
            version_output = await self.base().with_exec(["python", "--version"]).stdout()

            output += version_output 

            lint_output = await self.lint()

            output += lint_output

        return output
