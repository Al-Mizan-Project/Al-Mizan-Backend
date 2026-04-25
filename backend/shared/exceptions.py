from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}

ERROR_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "Bad request",
    status.HTTP_401_UNAUTHORIZED: "Authentication required",
    status.HTTP_403_FORBIDDEN: "Forbidden",
    status.HTTP_404_NOT_FOUND: "Resource not found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "Method not allowed",
    status.HTTP_409_CONFLICT: "Conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "Rate limit exceeded",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
}


def _extract_message(data, fallback):
    if isinstance(data, dict):
        detail = data.get("detail")
        if detail is not None:
            return str(detail)
        non_field_errors = data.get("non_field_errors")
        if isinstance(non_field_errors, list) and non_field_errors:
            return str(non_field_errors[0])
    if isinstance(data, list) and data:
        return str(data[0])
    if isinstance(data, str):
        return data
    return fallback


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return Response(
            {
                "error": {
                    "code": ERROR_CODES[status.HTTP_500_INTERNAL_SERVER_ERROR],
                    "message": ERROR_MESSAGES[status.HTTP_500_INTERNAL_SERVER_ERROR],
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    status_code = response.status_code
    payload = {
        "error": {
            "code": ERROR_CODES.get(status_code, "request_error"),
            "message": _extract_message(response.data, ERROR_MESSAGES.get(status_code, "Request failed")),
        }
    }

    if isinstance(response.data, dict):
        details = dict(response.data)
        if set(details.keys()) == {"detail"}:
            details = None
        if details:
            payload["error"]["details"] = details
    elif isinstance(response.data, list):
        payload["error"]["details"] = response.data

    response.data = payload
    return response
