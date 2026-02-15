"""
Custom logging filters for Django
"""
import logging


class SuppressIndexingProgressFilter(logging.Filter):
    """
    Filter out AJAX polling requests for indexing progress
    to reduce log spam while keeping important logs
    """
    def filter(self, record):
        # Suppress GET requests to /indexing-progress/
        message = record.getMessage()
        if '/indexing-progress/' in message and 'GET' in message:
            return False
        return True
