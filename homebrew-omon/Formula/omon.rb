class Omon < Formula
  include Language::Python::Virtualenv

  desc "Local-first monitoring and management tool for Ollama"
  homepage "https://github.com/LightbridgeLab/OllamaMon"
  url "https://github.com/LightbridgeLab/OllamaMon/archive/refs/tags/v0.5.0.tar.gz"
  sha256 "ffc521ec1f449e2a4a93b303f7e7519acf8523cdf853d1c31ebd116cfde28df5"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/omon --version")
  end
end
