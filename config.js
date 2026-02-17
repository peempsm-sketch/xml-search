const config = {
  inputDirs: ["./usb"],
  outputDir: "./copynew",

  mode: "or",
  caseSensitive: false,
  stopAfterFirstMatch: false,

  conditions: [
    { key: "TaxNumber", value: "Agent_4309cb39_VAL" },
    { key: "ReferenceNumber", value: "DUIR000108766" }
  ]
};

module.exports = config;
