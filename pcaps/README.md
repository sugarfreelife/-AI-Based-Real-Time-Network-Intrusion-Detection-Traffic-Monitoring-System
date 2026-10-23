# PCAP files

Place only authorized, local packet captures here for testing or demonstration. Packet capture files can contain sensitive information and are ignored by Git. Do not commit private traffic, credentials, or captures from networks you are not authorized to inspect.

For a no-capture local smoke demo, run `python -m scripts.synthetic_demo`. It creates `synthetic-demo-not-real-network.pcap`, a deterministic fixture of documentation-range addresses with SYN-only flows. The file is ignored by Git and is not real traffic or model evidence. Use `--force` to regenerate the same filename. The dashboard will show the synthetic filename and the rule-only alerts it triggers.
