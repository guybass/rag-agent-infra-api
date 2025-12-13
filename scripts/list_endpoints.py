#!/usr/bin/env python3
"""List all API endpoints with their methods, paths, and required fields."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from app.main import app


def get_endpoint_info(app: FastAPI):
    """Extract endpoint information from FastAPI app."""
    endpoints = []

    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            for method in route.methods:
                if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    endpoint = {
                        'method': method,
                        'path': route.path,
                        'name': route.name or '',
                        'tags': getattr(route, 'tags', []),
                    }

                    # Try to get request body model
                    if hasattr(route, 'dependant') and route.dependant.body_params:
                        for param in route.dependant.body_params:
                            if hasattr(param, 'type_') and hasattr(param.type_, '__fields__'):
                                fields = {}
                                for fname, field in param.type_.__fields__.items():
                                    required = field.required if hasattr(field, 'required') else True
                                    ftype = str(field.outer_type_).replace('typing.', '')
                                    fields[fname] = {
                                        'type': ftype,
                                        'required': required,
                                        'default': field.default if field.default is not None else None
                                    }
                                endpoint['body_fields'] = fields

                    # Get query params
                    if hasattr(route, 'dependant') and route.dependant.query_params:
                        query_fields = {}
                        for param in route.dependant.query_params:
                            query_fields[param.name] = {
                                'type': str(param.type_),
                                'required': param.required,
                                'default': param.default
                            }
                        endpoint['query_params'] = query_fields

                    endpoints.append(endpoint)

    return sorted(endpoints, key=lambda x: (x['path'], x['method']))


def print_endpoints(endpoints):
    """Print endpoints in a readable format."""
    print("=" * 80)
    print("RAG Agent Infrastructure API - Endpoint Reference")
    print("=" * 80)

    current_prefix = ""
    for ep in endpoints:
        # Group by API section
        parts = ep['path'].split('/')
        if len(parts) > 3:
            prefix = '/'.join(parts[:4])
        else:
            prefix = ep['path']

        if prefix != current_prefix:
            current_prefix = prefix
            print(f"\n{'─' * 80}")
            print(f"  {prefix}")
            print(f"{'─' * 80}")

        # Print method and path
        print(f"\n  {ep['method']:7} {ep['path']}")

        if ep.get('name'):
            print(f"          Name: {ep['name']}")

        # Print required body fields
        if ep.get('body_fields'):
            required = [f for f, v in ep['body_fields'].items() if v['required']]
            optional = [f for f, v in ep['body_fields'].items() if not v['required']]

            if required:
                print(f"          Required: {', '.join(required)}")
            if optional:
                print(f"          Optional: {', '.join(optional)}")

        # Print query params
        if ep.get('query_params'):
            params = [f"{k}{'*' if v['required'] else ''}" for k, v in ep['query_params'].items()]
            print(f"          Query: {', '.join(params)}")

    print(f"\n{'=' * 80}")
    print(f"Total endpoints: {len(endpoints)}")
    print("=" * 80)


def print_json(endpoints):
    """Print endpoints as JSON."""
    import json

    # Simplify for JSON output
    simple = []
    for ep in endpoints:
        item = {
            'method': ep['method'],
            'path': ep['path'],
        }
        if ep.get('body_fields'):
            item['body'] = {k: {'required': v['required'], 'type': v['type']}
                          for k, v in ep['body_fields'].items()}
        if ep.get('query_params'):
            item['query'] = ep['query_params']
        simple.append(item)

    print(json.dumps(simple, indent=2))


if __name__ == '__main__':
    endpoints = get_endpoint_info(app)

    if '--json' in sys.argv:
        print_json(endpoints)
    else:
        print_endpoints(endpoints)
