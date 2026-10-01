"""Unit tests for cross-platform path translation (Windows, macOS, Linux)."""

from generator.utils.path_utils import format_host_path, is_windows_path, is_git_bash_windows_path


def test_is_windows_path():
    """Verify detection of Windows drive and network paths."""
    assert is_windows_path(r"C:\Users\username\project\output") is True
    assert is_windows_path("C:/Users/username/project/output") is True
    assert is_windows_path(r"D:\output") is True
    assert is_windows_path(r"\\wsl$\Ubuntu\home\user") is True
    assert is_windows_path("/Users/username/project/output") is False
    assert is_windows_path("/home/ubuntu/project/output") is False


def test_is_git_bash_windows_path():
    """Verify detection of Git Bash / MinGW drive paths."""
    assert is_git_bash_windows_path("/c/Users/username/project/output") is True
    assert is_git_bash_windows_path("/d/projects/output") is True
    assert is_git_bash_windows_path("/Users/username/project/output") is False
    assert is_git_bash_windows_path("/home/user/project/output") is False


def test_format_host_path_macos_linux():
    """Test path translation for macOS and Linux host paths."""
    container_video = "/app/output/job-abc-123/job-abc-123.mp4"
    
    # macOS host
    mac_host = "/Users/heymac/x/stem-video-generator/output"
    assert format_host_path(container_video, host_output_dir=mac_host, container_output_dir="/app/output") == \
        "/Users/heymac/x/stem-video-generator/output/job-abc-123/job-abc-123.mp4"

    # Linux host
    linux_host = "/home/ubuntu/stem-video-generator/output"
    assert format_host_path(container_video, host_output_dir=linux_host, container_output_dir="/app/output") == \
        "/home/ubuntu/stem-video-generator/output/job-abc-123/job-abc-123.mp4"


def test_format_host_path_windows_backslash():
    """Test path translation for standard Windows host paths with backslashes."""
    container_video = "/app/output/job-abc-123/job-abc-123.mp4"
    win_host = r"C:\Users\John\stem-video-generator\output"
    
    result = format_host_path(container_video, host_output_dir=win_host, container_output_dir="/app/output")
    assert result == r"C:\Users\John\stem-video-generator\output\job-abc-123\job-abc-123.mp4"


def test_format_host_path_windows_forwardslash():
    """Test path translation for Windows host paths with forward slashes."""
    container_video = "/app/output/job-abc-123/job-abc-123.mp4"
    win_host = "C:/Users/John/stem-video-generator/output"
    
    result = format_host_path(container_video, host_output_dir=win_host, container_output_dir="/app/output")
    assert result == r"C:\Users\John\stem-video-generator\output\job-abc-123\job-abc-123.mp4"


def test_format_host_path_git_bash():
    """Test path translation for Git Bash format (/c/Users/...)."""
    container_video = "/app/output/job-abc-123/job-abc-123.mp4"
    git_bash_host = "/c/Users/John/stem-video-generator/output"
    
    result = format_host_path(container_video, host_output_dir=git_bash_host, container_output_dir="/app/output")
    assert result == "/c/Users/John/stem-video-generator/output/job-abc-123/job-abc-123.mp4"


def test_format_host_path_native_fallback():
    """Test fallback when running natively without Docker."""
    from pathlib import Path
    local_path = "./output/my_video.mp4"
    assert format_host_path(local_path, host_output_dir=None) == str(Path(local_path).resolve())
