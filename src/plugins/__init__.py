# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# Make the plugins directory a Python package
from .internal_knowledge_plugin import InternalKnowledgePlugin

__all__ = ["InternalKnowledgePlugin"]
