class NGSignError(Exception):
    """Base exception for all NGSign errors."""
    pass

class NGSignNotConfiguredError(NGSignError):
    """No active NGSignClientAccount found for this tenant."""
    pass

class NGSignAuthError(NGSignError):
    """JWT is invalid and could not be refreshed."""
    pass

class NGSignAPIError(NGSignError):
    """Unexpected error response from NGSign API."""
    pass

class NGSignSubmissionError(NGSignError):
    """Invoice submission to NGSign failed."""
    pass

class NGSignLockedInvoiceError(NGSignError):
    """Invoice is locked (already processed by TTN). Signed XML should be fetched directly."""
    pass
