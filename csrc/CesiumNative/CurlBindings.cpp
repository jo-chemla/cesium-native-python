#include <CesiumCurl/CurlAssetAccessor.h>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdlib>
#include <filesystem>
#include <memory>

namespace py = pybind11;

namespace {

// The CA bundle libcurl was built with is a compile-time path. The manylinux
// wheels bake in Red Hat's /etc/pki/tls/certs/ca-bundle.crt, so on Debian,
// Ubuntu, Arch or SUSE every HTTPS request fails with "Problem with the SSL CA
// cert" unless certificate_file is set. When the caller set nothing, use
// CURL_CA_BUNDLE or SSL_CERT_FILE if present (curl's own tool reads them, the
// library does not), else the first existing bundle at a well-known path.
void defaultCertificateFile(CesiumCurl::CurlAssetAccessorOptions& options) {
#if defined(__linux__)
  if (!options.certificateFile.empty() || !options.certificatePath.empty()) {
    return;
  }
  for (const char* var : {"CURL_CA_BUNDLE", "SSL_CERT_FILE"}) {
    const char* value = std::getenv(var);
    if (value != nullptr && *value != '\0') {
      options.certificateFile = value;
      return;
    }
  }
  for (const char* path :
       {"/etc/pki/tls/certs/ca-bundle.crt",      // Red Hat, Fedora
        "/etc/ssl/certs/ca-certificates.crt",   // Debian, Ubuntu, Arch
        "/etc/ssl/ca-bundle.pem",               // SUSE
        "/etc/ssl/cert.pem"}) {                 // Alpine, some BSD layouts
    std::error_code ec;
    if (std::filesystem::is_regular_file(path, ec)) {
      options.certificateFile = path;
      return;
    }
  }
#else
  (void)options;
#endif
}

} // namespace

void initCurlBindings(py::module& m) {
  py::class_<CesiumCurl::CurlAssetAccessorOptions>(
      m,
      "CurlAssetAccessorOptions")
      .def(py::init<>())
      .def_readwrite(
          "user_agent",
          &CesiumCurl::CurlAssetAccessorOptions::userAgent)
      .def_readwrite(
          "request_headers",
          &CesiumCurl::CurlAssetAccessorOptions::requestHeaders)
      .def_readwrite(
          "allow_directory_creation",
          &CesiumCurl::CurlAssetAccessorOptions::allowDirectoryCreation)
      .def_readwrite(
          "certificate_path",
          &CesiumCurl::CurlAssetAccessorOptions::certificatePath)
      .def_readwrite(
          "certificate_file",
          &CesiumCurl::CurlAssetAccessorOptions::certificateFile)
      .def_readwrite(
          "do_global_init",
          &CesiumCurl::CurlAssetAccessorOptions::doGlobalInit);

  py::class_<
      CesiumCurl::CurlAssetAccessor,
      CesiumAsync::IAssetAccessor,
      std::shared_ptr<CesiumCurl::CurlAssetAccessor>>(m, "CurlAssetAccessor")
      .def(
          py::init([](CesiumCurl::CurlAssetAccessorOptions options) {
            defaultCertificateFile(options);
            return std::make_shared<CesiumCurl::CurlAssetAccessor>(options);
          }),
          py::arg("options") = CesiumCurl::CurlAssetAccessorOptions(),
          "HTTP(S) accessor on libcurl. On Linux, when ``options`` names no "
          "certificate file or path, the CA bundle is taken from "
          "``CURL_CA_BUNDLE`` or ``SSL_CERT_FILE`` if set, else from the "
          "first existing well-known system bundle; the result is visible "
          "in ``options.certificate_file``.")
      .def_property_readonly(
          "options",
          &CesiumCurl::CurlAssetAccessor::getOptions,
          py::return_value_policy::reference_internal);
}
