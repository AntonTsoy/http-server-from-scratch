import socket
import threading
import gzip
import sys
import re


CLIENTS_QUEUE_SIZE = 3
KBYTE = 1024


def respond(status_code: int, reason_phrase: str, headers: str = "", content_type: str = "text/plain", body: str = "") -> bytes:
    content_length: int = len(body)  # Разберись, что сюда точно нужно писать
    respond_template: str = (
        f"HTTP/1.1 {status_code} {reason_phrase}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"{headers}"
        "\r\n"
        f"{body}"
    )
    return respond_template.encode("utf-8")


def handle_client_connection(client_socket: socket, buffer_size: int) -> None:
    while True:
        client_data: bytes = client_socket.recv(buffer_size)
        if not client_data:  # Нужен таймер. Если сообщений долго нет - разрыв
            print("Alert!", client_data)
            break

        request_headers: list[str] = client_data.decode("utf-8").splitlines()
        client_request: str = request_headers.pop(0)

        request_method, url = client_request.split()[:2]
        match (request_method):
            case "GET":
                make_get_response(client_socket, url, request_headers)
            case "POST":
                make_post_response(client_socket, url, request_headers)
            case _:
                raise ValueError("Client use unhandling http request method!")

    client_socket.close()


def make_get_response(client_socket: socket, url: str, request_headers: list[str]) -> None:
    url_parts: list[str] = url.split("/")
    headers = dict()
    for header in request_headers:
        if header:
            name, value = header.split(":", 1)
            headers[name.strip()] = value.strip()

    match url_parts[1]:
        case "":
            if len(url_parts) == 2:
                client_socket.send(respond("200", "OK", body="OK"))
            else:
                client_socket.send(respond("404", "Not Found", body="Not found"))
        case "echo":
            answer_content: str = url[6:]
            content_encoding = ""
            client_encoding_schemes: list[str] = headers.get("Accept-Encoding", '').split(', ')
            if "gzip" in client_encoding_schemes:
                answer_content = gzip.compress(answer_content.encode("utf-8"))
                content_encoding = "Content-Encoding: gzip\r\n"
            client_socket.send(respond("200", "OK", headers=content_encoding, body=answer_content))
        case "user-agent":
            client_socket.send(respond("200", "OK", body=headers["User-Agent"]))
        case "files":
            if len(sys.argv) > 2:
                directory: str = sys.argv[2]
            else:
                directory: str = "./"
            path_tale: str = "/".join(url_parts[2:])
            try:
                with open(directory + path_tale, "r", encoding="utf-8") as file:
                    content = file.read()
                    client_socket.send(respond("200", "OK", content_type="application/octet-stream", body=content))
            except FileNotFoundError:
                client_socket.send(respond("404", "Not Found", body="Not found"))
        case _:
            client_socket.send(respond("404", "Not Found", body="Not found"))


def make_post_response(client_socket: socket, url: str, request_tale: list[str]) -> None:
    url_parts: list[str] = url.split("/")
    match url_parts[1]:
        case "files":
            if len(sys.argv) > 2:
                directory: str = sys.argv[2]
            else:
                directory: str = "./"
            path_tale: str = "/".join(url_parts[2:])

            request_body: str = request_tale[-1]
            pattern: str = r"Content-Length: \d+"
            content_length: int = 0
            for header in request_tale[:-1]:
                match = re.search(pattern, header)
                if match:
                    content_length = int(match[0].split(":")[1])
                    break

            with open(directory + path_tale, "w", encoding="utf-8") as file:
                file.write(request_body[-content_length:])
                client_socket.send("HTTP/1.1 201 Created\r\n\r\n".encode())


def main() -> None:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", 4221))
    server_socket.listen(CLIENTS_QUEUE_SIZE)

    while True:
        client_socket, address = server_socket.accept()
        print(f"The {address} user was connected.")
        threading.Thread(target=handle_client_connection, args=(client_socket, 10*KBYTE)).start()


if __name__ == "__main__":
    main()
