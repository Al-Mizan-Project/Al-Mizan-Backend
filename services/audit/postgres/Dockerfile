FROM postgres:15
 
# Copy our custom config
COPY postgresql.conf /etc/postgresql/postgresql.conf
 
# Tell postgres to use our config file
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
