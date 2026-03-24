"""
News Module - News fetching, generation, and web search functionality
"""
from .generator import NewsGenerator
from .fetcher import NewsFetcher
from .summarizer import Summarizer
from .agent import TopicNewsAgent
from .web_search import WebSearchTool, get_search_tool_definition


__all__ = [
    'NewsGenerator',
    'NewsFetcher',
    'Summarizer',
    'TopicNewsAgent',
    'WebSearchTool',
    'get_search_tool_definition',
]
