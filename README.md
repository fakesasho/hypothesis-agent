# Hypothesis Agent

The Hypothesis Agent is a Python command line application that utilises an LLM to query and analyse data from the 
biomedical domain, specifically the [GAF](https://geneontology.org/docs/go-annotation-file-gaf-format-2.0/) of the human
genome and a few [KAGG](https://www.genome.jp/kegg/pathway.html)-encoded disease pathways.

## Installation

Set your OpenAI API key in the `OPENAI_API_KEY` environment variable.

```bash
export OPENAI_API_KEY=your-api-key
```

The easy way to install the agent is to use the provided Makefile..
```bash
make install
```

### Specific Makefile commands

- `make install` - Install the agent
- `make prepare-directories` - Prepare the directories for the neo4j database
- `make download-apoc` - Download the APOC plugin
- `make download-gds` - Download the GDS plugin
- `make create-neo4j-container` - Create the neo4j container
- `make run-neo4j` - Start the neo4j container
- `make stop-neo4j` - Stop the neo4j container
- `make wipe-data` - Wipe the neo4j data
- `make import-data` - Import the data
- `make reset-neo4j` - Reset the neo4j database
- `make test-neo4j` - Test the neo4j connection
- `make test` - Run the tests
- `make test-fast` - Run the tests except the slow ones
- `make install-requirements` - Install the requirements
- `make run` - Run the agent

## Usage

The agent will keep a conversation on any topic but if the user asks about the biomedical domain, the agent will switch
to a more specific mode and query the biomedical data in order to generate a hypothesis. Typically, the agent will
make a plan for how to gather data and then execute the plan. Finally, the agent will generate a hypothesis based on the
gathered data.

### Running the agent

The agent can be run with the following command:
```bash
make run
```

Or if you want the python command:
```bash
python -m ha -W ignore
```

### Some useful prompts

```commandline
you: Tell me about INSR gene and what it impacts in the diabetes pathway.
```

```commandline
you: Explain the impact of the MLH1 gene on colorectal cancer risk.
```

```commandline
you: What role does the GLUT4 gene play in glucose uptake and diabetes?
```

### The tools that the agent uses

- Neo4j - The agent uses a Neo4j database to store the KEGG pathways data (kegg_query)
- GAF - The agent uses the GAF file to query the human genome data
- Graph Analysis - The agent uses a custom graph analysis script to generate a hypothesis about the impact of a gene on a pathway

## Architecture


![Architecture](img/ha-high-level.png)
![Core](img/ha-core.png)
![QueryExec](img/ha-query-executor.png)

## Configuration

There are a bunch of things you can change with environment variables. There is no need to do it in order to run 
the agent though (except OpenAI's key of course). Here are the most important ones:

* `NEO4J_URI` - The URI of the Neo4j database
* `NEO4J_USER` - The username of the Neo4j database
* `NEO4J_PASSWORD` - The password of the Neo4j database
* `OPENAI_API_KEY` - The OpenAI API key
* `OPENAI_NEO4J_MODEL` - The OpenAI model to use for the Neo4j queries
* `OPENAI_PANDAS_MODEL` - The OpenAI model to use for the Pandas queries
* `OPENAI_AGENT_MODEL` - The OpenAI model to use for the agent queries
* `OPENAI_API_KEY` - The OpenAI API key

## Environment info
```bash
LSB Version:    core-11.1.0ubuntu4-noarch:security-11.1.0ubuntu4-noarch
Distributor ID: Ubuntu
Description:    Ubuntu 22.04.2 LTS
Release:        22.04
Codename:       jammy
Python 3.10.14
Architecture:                    x86_64
CPU op-mode(s):                  32-bit, 64-bit
Address sizes:                   39 bits physical, 48 bits virtual
Byte Order:                      Little Endian
CPU(s):                          4
On-line CPU(s) list:             0-3
Vendor ID:                       GenuineIntel
Model name:                      Intel(R) Core(TM) i5-4460  CPU @ 3.20GHz
CPU family:                      6
Model:                           60
Thread(s) per core:              1
Core(s) per socket:              4
Socket(s):                       1
Stepping:                        3
CPU max MHz:                     3400.0000
CPU min MHz:                     800.0000
BogoMIPS:                        6385.19
Flags:                           fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp lm constant_tsc arch_perfmon pebs bts rep_good nopl xtopology nonstop_tsc cpuid aperfmperf pni pclmulqdq dtes64 monitor ds_cpl vmx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm cpuid_fault invpcid_single pti ssbd ibrs ibpb stibp tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid xsaveopt dtherm ida arat pln pts md_clear flush_l1d
Virtualisation:                  VT-x
L1d cache:                       128 KiB (4 instances)
L1i cache:                       128 KiB (4 instances)
L2 cache:                        1 MiB (4 instances)
L3 cache:                        6 MiB (1 instance)
NUMA node(s):                    1
NUMA node0 CPU(s):               0-3
Vulnerability Itlb multihit:     KVM: Mitigation: VMX disabled
Vulnerability L1tf:              Mitigation; PTE Inversion; VMX conditional cache flushes, SMT disabled
Vulnerability Mds:               Mitigation; Clear CPU buffers; SMT disabled
Vulnerability Meltdown:          Mitigation; PTI
Vulnerability Mmio stale data:   Unknown: No mitigations
Vulnerability Retbleed:          Not affected
Vulnerability Spec store bypass: Mitigation; Speculative Store Bypass disabled via prctl and seccomp
Vulnerability Spectre v1:        Mitigation; usercopy/swapgs barriers and __user pointer sanitization
Vulnerability Spectre v2:        Mitigation; Retpolines, IBPB conditional, IBRS_FW, STIBP disabled, RSB filling, PBRSB-eIBRS Not affected
Vulnerability Srbds:             Mitigation; Microcode
Vulnerability Tsx async abort:   Not affected
               total        used        free      shared  buff/cache   available
Mem:            31Gi       4.6Gi       2.0Gi        32Mi        24Gi        26Gi
Swap:           15Gi       1.2Gi        14Gi
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           3.2G  3.4M  3.2G   1% /run
/dev/sda1        95G   28G   62G  31% /
tmpfs            16G   60K   16G   1% /dev/shm
tmpfs           5.0M     0  5.0M   0% /run/lock
/dev/sdc        470G  122G  324G  28% /home
/dev/sdb        1.8T  1.5T  256G  86% /store/hdd/big
/dev/sdd        917G   90G  782G  11% /store/hdd/small
overlay         1.8T  1.5T  256G  86% /store/hdd/big/docker/overlay2/7acd4b332d3010aab7e443cbd00d897e4d392607764f1c630dd973bc43639845/merged
overlay         1.8T  1.5T  256G  86% /store/hdd/big/docker/overlay2/2f585f84cb2ecc2a6dae658b812e4ebb447070e9653ae81f8516842dec733b96/merged
overlay         1.8T  1.5T  256G  86% /store/hdd/big/docker/overlay2/b373df3d03bc895d7ebfb64bb301b7ca97c8e816826a407cc8ef6bab8163f855/merged
tmpfs           3.2G  8.0K  3.2G   1% /run/user/1000
tmpfs            16G  432K   16G   1% /run/qemu
overlay         1.8T  1.5T  256G  86% /store/hdd/big/docker/overlay2/2768dce6d02ea3f31cfbdab7af0b47fbb247b3f28bcd0c0cd82f44933cbe11ec/merged
Linux bacon 5.15.0-76-generic #83-Ubuntu SMP Thu Jun 15 19:16:32 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux
```
