import authum.duo
import authum.http


def test_duo_start_server(random_url, random_string):
    name = "Test"
    http = authum.http.HTTPClient()
    duo = authum.duo.DuoWebV2(
        name=name,
        http_client=http,
        host=random_url,
        sig_request=random_string,
        post_action=f"{random_url}/test",
    )
    assert duo.server_url == ""

    duo.start_server()
    response = http.http_request(url=duo.server_url)
    assert f"<title>{name}" in response.text
