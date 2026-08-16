from b2b_serv.runtime import configure_tk_environment

configure_tk_environment()

from b2b_serv.app import run


if __name__ == "__main__":
    run()
