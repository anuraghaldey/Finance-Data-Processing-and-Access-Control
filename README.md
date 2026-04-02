# Finance-Data-Processing-and-Access-Control
A backend for a finance dashboard system where different users can interact with financial records based on their roles.The system supports the storage and management of financial entries, user roles, permissions, and summary level analytics. This backend is logically structured and able to serve data to a frontend dashboard in an efficient way.


The app is designed stateless (JWT auth, no server-side sessions) so it can scale horizontally behind a load balancer. Redis is externalized for cache and token blocklist,
meaning multiple app instances can share state. In production, an Nginx reverse proxy or AWS ALB would distribute traffic across Gunicorn instances.
