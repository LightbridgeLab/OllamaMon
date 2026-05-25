class Omon < Formula
  include Language::Python::Virtualenv

  desc "Local-first monitoring and management tool for Ollama"
  homepage "https://github.com/LightbridgeLab/OllamaMon"
  url "https://github.com/LightbridgeLab/OllamaMon/archive/refs/tags/v0.6.2.tar.gz"
  sha256 "7e0e5e952afc792acd92b2fabacdf8230f82bd88a0b2c512b24cee81bea41bde"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/omon --version")
  end
end
