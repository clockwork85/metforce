# MetForce Documentation: NetCDF Output and Provenance Tracking

## Table of Contents

1. [Introduction: Why NetCDF and Provenance Matter](#introduction)
2. [Understanding MetForce NetCDF Files](#understanding-netcdf)
3. [Provenance Tracking System](#provenance-system)
4. [User Guide: Common Workflows](#user-guide)
5. [Developer Guide: Extending MetForce](#developer-guide)
6. [Visualization and Analysis](#visualization)
7. [Best Practices and Troubleshooting](#best-practices)

---

## 1. Introduction: Why NetCDF and Provenance Matter {#introduction}

MetForce has evolved from producing simple text-based meteorological files to generating rich, self-documenting NetCDF files with comprehensive provenance tracking. This evolution addresses a fundamental challenge in scientific computing: **data without context loses its value over time**.

### The Problem MetForce Solves

Imagine you are reviewing a research project from three years ago. You find a meteorological forcing file used in your model simulations, but you cannot remember where the temperature data came from. Was it measured at a weather station? Which instrument? Was it from a reanalysis product like NLDAS-2? Were any corrections applied? Without this information, you cannot assess the data's quality, cannot reproduce your results, and cannot confidently build upon your previous work.

This scenario plays out constantly in scientific research. Data files get passed between colleagues, archived for regulatory requirements, or revisited years later for new studies. When the metadata travels separately from the data (or worse, exists only in someone's memory), the scientific value degrades rapidly.

### Why NetCDF?

NetCDF, which stands for Network Common Data Form, is a self-describing binary format that stores both data and metadata together in a single file. When you open a NetCDF file, you immediately see what variables it contains, what their units are, when the data was collected, and crucially, where it came from and how it was processed. This makes NetCDF files inherently more valuable for long-term research because they carry their own documentation.

The Climate and Forecast conventions, commonly called CF conventions, provide a standardized vocabulary for atmospheric and oceanic data. When MetForce creates a CF-compliant NetCDF file, it means that any software tool that understands CF conventions can immediately work with your data. Tools like Panoply for visualization, xarray for analysis in Python, or NCO for command-line processing all speak this common language.

### What is Provenance Tracking?

Provenance tracking means documenting the complete history of how data was created, processed, and modified. In MetForce, this means every variable in your NetCDF file carries rich metadata explaining:

- **Where did this data come from?** Was it measured at a weather station, derived from satellite observations, or extracted from a reanalysis product?
- **What instrument or model produced it?** If it is station data, which specific sensor? If it is modeled data, which system and version?
- **How was it processed?** Were corrections applied? Was it spatially interpolated? What algorithms were used?
- **What is its quality?** Are there gaps in the data? Were outliers filtered? What uncertainties exist?

This documentation travels with the data forever. A colleague who receives your NetCDF file can immediately understand its provenance without needing to ask you. A reviewer assessing your research can verify your data sources. You can revisit your own work years later and know exactly what data you used.

### MetForce's Three-Phase Provenance System

MetForce implements provenance tracking through a progressive enhancement system with three phases:

**Phase 1** established the basic NetCDF infrastructure, ensuring files were CF-compliant and contained the essential structural metadata. This gave MetForce the foundation to build upon.

**Phase 2** added an instrument library system, allowing station data to be linked to detailed specifications of the sensors that measured it. This means your NetCDF file can document not just that temperature was measured, but that it was measured by a Vaisala HMP155 thermohygrometer with known accuracy specifications.

**Phase 3**, which we have just completed, implements automatic provenance generation. The system now introspects your data sources and automatically populates rich metadata for each variable. If you pull data from NLDAS-2, the system documents the model details, spatial resolution, and data assimilation methodology. If you use pvlib to compute solar positions, it documents the calculation method and references.

The key insight is that provenance should be automatic. Users should get comprehensive documentation for free, without having to manually write metadata. The system understands your data pipeline and documents it for you.

---

## 2. Understanding MetForce NetCDF Files {#understanding-netcdf}

### File Structure and Organization

A MetForce NetCDF file organizes meteorological data as a collection of time-series variables. Each variable represents a different meteorological quantity measured or modeled at regular time intervals. The file structure follows a straightforward pattern that makes it easy to understand and work with.

At the highest level, the file contains three main components: dimensions, coordinates, and data variables. The dimensions define the shape of the data. For meteorological time series, the primary dimension is time, which defines how many observations exist in the file. If your file contains hourly data for a full year, the time dimension would be 8760 (the number of hours in a non-leap year).

Coordinates provide the actual values along each dimension. The time coordinate contains timestamps for each observation, typically stored as seconds since a reference date (the Unix epoch of January 1, 1970). This numeric representation makes time calculations efficient while remaining unambiguous about what each timestamp represents.

Data variables contain the actual meteorological measurements or model outputs. Each variable is an array indexed by the time dimension, so `air_temperature[0]` gives you the temperature at the first timestamp, `air_temperature[1]` at the second timestamp, and so forth. Every data variable carries attributes that describe what it represents, what units it uses, and where it came from.

### CF Standard Names: A Common Vocabulary

The Climate and Forecast conventions define standard names for thousands of atmospheric and oceanic quantities. These standard names provide an unambiguous way to identify what a variable represents, independent of what you choose to call it in the file.

For example, the standard name `air_temperature` always means the temperature of the air, measured in an agreed-upon way. This is more precise than calling it "temp" or "T" or "temperature," all of which could be ambiguous. When software encounters the standard name `air_temperature`, it knows exactly what the variable represents and can make intelligent decisions about how to display or analyze it.

MetForce uses standard names consistently throughout its NetCDF files. Here are the mappings MetForce uses for common meteorological variables:

Air pressure uses the standard name `air_pressure` and must be expressed in Pascals. MetForce converts from millibars automatically during NetCDF creation because CF conventions require SI units. Air temperature uses `air_temperature` in degrees Celsius. While the CF conventions prefer Kelvin for temperature, degrees Celsius is an accepted alternative that matches the conventions used in meteorological practice.

Relative humidity uses `relative_humidity` and is stored as a dimensionless fraction between zero and one, rather than as a percentage. This avoids ambiguity about whether eighty percent humidity should be stored as 80 or 0.8. Wind speed uses `wind_speed` in meters per second, and wind direction uses `wind_from_direction` in degrees, where zero degrees means wind from the north and degrees increase clockwise (so 90 degrees means wind from the east).

Precipitation uses `precipitation_amount` in kilograms per square meter, which happens to be numerically equivalent to millimeters of water. This reflects the accumulation over the time interval rather than an instantaneous rate.

Solar radiation variables have particularly precise standard names. Global horizontal irradiance uses `surface_downwelling_shortwave_flux_in_air`, direct normal irradiance (DNI) uses `surface_direct_along_beam_shortwave_flux_in_air`, and diffuse horizontal irradiance uses `surface_diffuse_downwelling_shortwave_flux_in_air`. The verbosity of these names reflects the need to be absolutely precise about what component of solar radiation is being measured and in what orientation.

### Global Attributes: File-Level Metadata

Every NetCDF file has global attributes that describe the file as a whole rather than individual variables. MetForce populates these attributes to document when and how the file was created, what conventions it follows, and where the data applies spatially.

The `Conventions` attribute declares that the file follows CF-1.10 conventions. Software tools use this to know how to interpret the file's structure and metadata. The `title` attribute provides a human-readable description of what the file contains, typically something like "Vidalia, Louisiana NLDAS-2 Data for 2025."

Spatial coverage is documented through `geospatial_latitude`, `geospatial_longitude`, and `geospatial_vertical_min` (elevation). These tell you exactly where the data applies, which is essential for meteorological data since conditions vary dramatically with location.

The `source` attribute documents the primary data source, automatically detected from your configuration. If you use station data, it will say "station." If you use NLDAS-2, it will say "nldas2." Mixed-source files document the combination. The `processing_level` indicates how processed the data is, with "2" meaning quality-controlled and derived products, which is typical for MetForce output.

Temporal coverage is documented through `time_coverage_start` and `time_coverage_end` in ISO 8601 format, making it instantly clear what time period the file spans. The `history` attribute logs when and how the file was created, providing a permanent audit trail.

### Variable Attributes: Provenance and Context

While global attributes describe the file as a whole, each variable has its own set of attributes that document its specific provenance and characteristics. This is where MetForce's automatic provenance system shines.

Every variable includes basic descriptive attributes: `standard_name` provides the CF standard name, `long_name` gives a human-readable description, and `units` specifies the measurement units using the UDUNITS syntax. The `cell_methods` attribute documents how the value relates to the time interval, with "time: mean" indicating the value represents an average over the interval (typical for temperature or wind speed) and "time: sum" indicating accumulation over the interval (typical for precipitation).

The provenance attributes tell the story of where the data came from and how it was created. The `source` attribute identifies the data source as "station," "nldas2," "pvlib," or another provider. The `data_type` classifies the data as "measurement" (directly observed), "reanalysis" (model with data assimilation), "derived" (calculated from other variables), or "model" (pure model output without assimilation).

For station data, instrument documentation becomes crucial. The `instrument_manufacturer`, `instrument_model`, and `serial_number` attributes link the measurement to a specific sensor. The `installation_height` documents where the sensor was mounted, which matters enormously for quantities like wind speed that vary with height.

For reanalysis products like NLDAS-2, the system documents the model name, spatial resolution, temporal resolution, and the data assimilation system used. The `comment` attribute provides a narrative explanation of how the data was created, such as "Derived from NLDAS-2 reanalysis data. Spatially interpolated to site location. Hourly temporal resolution."

For derived quantities computed by MetForce, the `method` attribute documents the calculation algorithm. For solar radiation partitioning, this might say "Clear-sky fraction method using cosine of solar zenith angle" to explain exactly how direct and diffuse components were separated.

The `references` attribute points to documentation, DOIs, or scientific papers that describe the methodology or data source in detail. For NLDAS-2 data, this includes the DOI for the JCLI paper describing the system. For pvlib calculations, it includes the URL for the pvlib documentation.

Quality information appears in the `quality_assessment` attribute, which documents data completeness, any gaps, and overall quality. For consistent high-quality data, this simply states "All values consistent quality." For datasets with issues, it documents the problems, such as "Data coverage: 85%. Missing values during instrument maintenance periods."

### Time Representation and Bounds

Time in NetCDF files requires careful attention because meteorological data can represent instantaneous measurements, interval averages, or accumulations over periods. MetForce handles this using the CF conventions for time bounds.

The time coordinate itself represents the timestamp associated with each observation, stored as seconds since January 1, 1970 (Unix epoch). This makes calculations efficient and avoids ambiguities about time zones or calendar systems. The `time` variable includes a `bounds` attribute pointing to a `time_bnds` variable that documents the start and end of each time interval.

For hourly data, if the time coordinate says "2025-01-01 01:00:00," the time bounds might show the interval runs from "2025-01-01 00:00:00" to "2025-01-01 01:00:00." This tells you that a temperature of 15°C at that timestamp represents the average temperature over that hour, not an instantaneous measurement at 1:00 AM.

The bounds comment clarifies that intervals are left-closed and right-open, meaning they include the start time but not the end time. This convention prevents double-counting at boundaries and makes it unambiguous how intervals relate to each other.

For variables with `cell_methods = "time: sum"` like precipitation, the bounds are especially important. A precipitation value of 2.5 mm at timestamp "2025-01-01 01:00:00" with bounds from 00:00 to 01:00 means 2.5 mm fell during that one-hour period.

---

## 3. Provenance Tracking System {#provenance-system}

### Design Philosophy: Automatic Documentation

The core principle behind MetForce's provenance system is that documentation should happen automatically as a side effect of your normal workflow. You should not need to remember to document things, manually fill in metadata fields, or maintain separate documentation files. Instead, the system should understand what you are doing and document it for you.

This approach stems from a simple observation: manual documentation inevitably gets skipped. When you are rushing to meet a deadline, when you are doing exploratory analysis, or when you are modifying code that you think you will throw away (but end up keeping), manual documentation falls by the wayside. The only reliable way to ensure consistent, comprehensive documentation is to make it automatic.

MetForce achieves this through a technique called introspection. When you configure MetForce to pull temperature data from NLDAS-2, the system knows that NLDAS-2 is a specific reanalysis product with known characteristics. It knows the spatial resolution, temporal resolution, model system, and documentation references. It automatically populates all this information into the NetCDF file without you having to specify it.

When you use the instrument library to document that your temperature sensor is a Vaisala HMP155, the system looks up that instrument's specifications and includes them in the metadata. It knows the manufacturer, model number, accuracy specifications, and recommended installation practices. All this information flows into the NetCDF file automatically.

The system also makes it easy to augment the automatic documentation with your own notes. If you want to mention that the sensor was recently calibrated, that the site experienced unusual conditions during the measurement period, or that you applied a specific correction, you can add these details through the metadata configuration. Your additions supplement rather than replace the automatic documentation.

### Source-Specific Provenance

MetForce recognizes that different data sources require different types of documentation. Station measurements need instrument details. Reanalysis products need model specifications. Derived quantities need algorithm documentation. The provenance system adapts its documentation to match the data source.

For station data, the system focuses on instrument provenance. It documents the specific sensor that made each measurement, including manufacturer, model, and serial number when available. It notes the installation height, which matters enormously for wind measurements but less so for temperature. It documents the sensor's accuracy specifications and valid measurement ranges.

The system also documents measurement characteristics specific to each sensor type. For pyranometers measuring solar radiation, it notes the spectral response, whether the sensor has heating to prevent frost and dew accumulation, and the manufacturer's stated uncertainty. For thermohygrometers measuring temperature and humidity, it documents the sensor's response time and whether it uses active ventilation to minimize radiation errors.

For NLDAS-2 data, the provenance shifts to model characteristics. The system documents that NLDAS-2 is "North American Land Data Assimilation System," that it uses a specific atmospheric model forced by observations, and that it produces gridded outputs at 1/8th degree (approximately 12.5 km) spatial resolution with hourly temporal resolution. It notes that the data was spatially interpolated from the NLDAS-2 grid to your specific location.

The system includes a reference to the peer-reviewed paper describing NLDAS-2's methodology, giving users a pathway to understand the data assimilation system, model physics, and validation studies. This contextualizes the data's quality and appropriate uses.

For solar position calculations using pvlib, the system documents that these are derived geometric calculations rather than measurements. It notes the calculation method (pvlib.solarposition), the required inputs (latitude, longitude, and time), and provides a reference to the pvlib documentation. This distinguishes calculated solar positions from measured solar radiation, which could be confused without proper documentation.

For derived quantities like partitioning global solar radiation into direct and diffuse components, the system documents the algorithm used. If you use the clear-sky fraction method, it explains that the partitioning is based on the cosine of the solar zenith angle and provides the fraction parameter used. If you compute beam horizontal irradiance from direct normal irradiance, it documents the geometric transformation applied.

### Instrument Library System

The instrument library provides a centralized repository of sensor specifications that can be referenced throughout your meteorological data processing. Rather than typing in instrument details every time you create a dataset, you define each instrument once in the library and then reference it by name in your configuration files.

The library organizes instruments by category: pyranometers for measuring total solar radiation, pyrheliometers for measuring direct normal radiation, thermohygrometers for measuring temperature and humidity, barometers for measuring pressure, anemometers for measuring wind, and rain gauges for measuring precipitation. This categorization helps you find relevant instruments quickly and ensures you are using an appropriate instrument type for each measurement.

Each instrument entry includes comprehensive metadata that follows a structured schema. The manufacturer and model identify the specific sensor. The category links it to the type of measurement. The description provides human-readable context about the sensor's characteristics and typical applications.

The specifications section documents the sensor's measurement capabilities. For a pyranometer, this includes the spectral range (typically 300 to 3000 nm for shortwave radiation), response time, and whether it has internal heating. For a thermohygrometer, it includes the temperature range, temperature accuracy, humidity range, humidity accuracy, and response time. These specifications help users understand the data quality and limitations.

Installation recommendations provide guidance on proper sensor deployment. For pyranometers, this might note the need for level mounting and unobstructed sky view. For anemometers, it specifies the recommended installation height and clearance from obstacles. These recommendations help ensure measurements meet quality standards.

MetForce ships with a default instrument library containing commonly used sensors: several models of Apogee pyranometers, the Eppley Normal Incidence Pyrheliometer, Vaisala and Campbell Scientific thermohygrometers, Vaisala and Setra barometers, R.M. Young anemometers, and Texas Electronics rain gauges. This covers most standard meteorological station configurations.

You can extend the library with your own instruments by creating a custom library file in TOML format. This file follows the same schema as the default library, allowing you to document specialized sensors, custom calibrations, or sensors with site-specific notes. Your custom library merges with the default library, so you have access to both standard instruments and your additions.

When you reference an instrument in your configuration file, the system looks it up in the combined library and includes all relevant specifications in the NetCDF file's metadata. This means every measurement in your NetCDF file carries a complete record of what instrument produced it and what its characteristics are.

### Configuration-Based Metadata

While automatic provenance covers most documentation needs, you sometimes need to add site-specific or application-specific details that the system cannot infer. The configuration-based metadata system lets you augment the automatic documentation with your own information.

Each variable in your configuration file can include a metadata section that specifies additional attributes. The most common addition is a comment that provides context about the specific measurement or calculation. You might note that a sensor was recently calibrated, that measurements during a certain period should be treated with caution, or that you applied a specific correction factor.

The system intelligently merges your custom metadata with the automatic documentation. For most attributes, your custom values augment the automatic ones. If the system generates a comment explaining that data came from NLDAS-2, and you add a comment noting a specific characteristic of your analysis, both comments appear in the final metadata. This ensures you do not accidentally lose important documentation.

For some attributes, you might want to completely replace the automatic documentation rather than augment it. The `comment_replace` field lets you provide a comment that overrides the automatic comment entirely. This is useful when you have transformed the data in ways that make the automatic description misleading.

You can also add completely custom attributes that have no automatic equivalent. If you want to document a funding source, a quality control procedure you applied, or a contact person for questions about the data, you can add these as arbitrary attributes in the metadata section. The system passes them through to the NetCDF file unchanged.

When you use the instrument library, you can reference instruments by name in the metadata section. The system expands this reference to include all the instrument's specifications. You can also override specific instrument fields if you need to document a modified version or a sensor with non-standard characteristics.

This flexible system means you can start with minimal configuration and get comprehensive automatic documentation, then progressively add more specific details as needed. For quick exploratory work, the automatic documentation suffices. For final published results, you can add detailed context and attribution.

### Quality Assessment Documentation

Data quality is a critical but often neglected aspect of metadata. MetForce includes quality assessment information automatically, with the level of detail scaling to match the complexity of your data.

For high-quality, complete datasets, the quality assessment is simple: "All values consistent quality." This tells users that the data appears reliable and complete without cluttering the metadata with unnecessary details. It is an affirmative statement that someone checked the data rather than an admission that the data has not been examined.

When data has known issues, the quality assessment becomes more detailed. If your dataset has missing values, the system notes the data coverage percentage and explains the gaps. "Data coverage: 85%. Missing values during instrument maintenance periods" tells users that 15 percent of the expected observations are missing and provides context about why.

For datasets with multiple quality levels, you might note that some periods have higher uncertainty. "Good quality data except for January 15-20 when sensor ventilation fan malfunctioned. Temperature readings during this period may be 1-2°C higher than actual due to radiation heating." This detailed assessment helps users decide whether to exclude the affected period or apply corrections.

The quality assessment complements rather than replaces formal quality control flags. For simple datasets where quality is consistent throughout, the text description suffices. For complex datasets where quality varies by observation, you would add separate quality control variables with per-observation flags. MetForce's Phase 5 development will implement these formal QC variables when needed.

---

## 4. User Guide: Common Workflows {#user-guide}

### Creating Your First NetCDF Met File

Let me walk you through creating a complete NetCDF meteorological file from scratch, explaining each decision along the way.

Start by creating a configuration file that describes your data source and what you want to produce. We will call this file `my_site_config.toml`. At minimum, you need to specify the location, time range, and data sources. Here is a complete minimal configuration:

```toml
[required]
latitude = 35.5
longitude = -80.8
elevation = 250.0
start_range = "2024-01-01 00:00"
end_range = "2024-12-31 23:00"

[optional]
outfile = "my_site_2024.nc"
location_name = "My Weather Station"
freq = "1h"

[parameters.temperature]
source = "nldas2"

[parameters.pressure]
source = "nldas2"

[parameters.relative_humidity]
source = "nldas2"

[parameters.wind_speed]
source = "nldas2"

[parameters.wind_direction]
source = "nldas2"

[parameters.precipitation]
source = "nldas2"

[parameters.global_shortwave]
source = "nldas2"

[parameters.downwelling_lwir]
source = "nldas2"
```

This configuration tells MetForce to create a file with hourly meteorological data for 2024 at a location in North Carolina, pulling all variables from the NLDAS-2 reanalysis product. When you run MetForce with this configuration, it will automatically fetch the NLDAS-2 data, interpolate it to your specific location, and create a CF-compliant NetCDF file with full provenance documentation.

Each parameter section specifies a single meteorological variable and where its data comes from. The `source` field tells MetForce what data source to use. For this example, we are using "nldas2" for everything, which means North American Land Data Assimilation System 2, a high-quality reanalysis product covering North America.

When you run this configuration, MetForce will connect to NASA's Earth data servers, search for NLDAS-2 data covering your time range, download the necessary files, extract data for your specific location, and assemble it into a single NetCDF file with comprehensive metadata. The resulting file will document that every variable came from NLDAS-2, specify the model details, note the spatial interpolation that was performed, and include references to the NLDAS-2 documentation.

### Adding Solar Radiation Components

Most meteorological applications need more detailed solar radiation information than just global horizontal irradiance. Let me show you how to add direct and diffuse components, which are essential for solar energy applications and many ecological models.

Expand your configuration to include derived solar radiation:

```toml
[parameters.global_shortwave]
source = "nldas2"

[parameters.direct_shortwave]
source = "global_coszenith"
fraction = 0.95

[parameters.diffuse_shortwave]
source = "global_coszenith"

[parameters.zenith]
source = "pvlib"

[parameters.azimuth]
source = "pvlib"
```

This configuration demonstrates MetForce's ability to derive quantities from other variables. The `global_coszenith` source implements a simple but effective partitioning algorithm that separates global radiation into direct and diffuse components based on solar position.

The algorithm works by computing a clear-sky fraction using the cosine of the solar zenith angle. When the sun is high in the sky (low zenith angle), the clear-sky fraction is high, and most of the global radiation is direct. When the sun is near the horizon (high zenith angle), the clear-sky fraction is low, and more of the radiation is diffuse due to increased atmospheric scattering.

The `fraction` parameter (0.95 in this example) adjusts the sensitivity of the partitioning. A value of 0.95 means that under perfectly clear skies with the sun directly overhead, 95 percent of the global radiation would be classified as direct. Lower values make the algorithm more conservative, classifying more radiation as diffuse. You can tune this parameter based on your local climate and sky conditions.

The solar position variables (zenith and azimuth) specify `source = "pvlib"`, which tells MetForce to compute them using the pvlib library's high-accuracy solar position algorithms. These calculations require only your location and timestamp, producing geometric positions that are valid anywhere on Earth at any time.

When you run this configuration, the provenance system documents the entire calculation chain. The global radiation metadata notes it came from NLDAS-2. The direct and diffuse radiation metadata explain they were derived from global radiation using the cosine zenith partitioning method, reference the algorithm, and note the fraction parameter used. The solar position metadata documents that the positions were calculated using pvlib.solarposition and provides a reference to the pvlib documentation.

### Incorporating Station Measurements

Real-world meteorological work often combines model data with station observations. Let me show you how to create a hybrid file that uses high-quality station measurements where available and fills in other variables from reanalysis.

Suppose you have a weather station that measures temperature, humidity, and wind with high-quality instruments, but you need to get pressure, precipitation, and radiation from NLDAS-2. Your configuration would look like this:

```toml
[required]
latitude = 35.5
longitude = -80.8
elevation = 250.0
start_range = "2024-01-01 00:00"
end_range = "2024-12-31 23:00"

[optional]
outfile = "hybrid_site_2024.nc"
location_name = "Hybrid Station/NLDAS2"
metfile = "station_data_2024.met"

[parameters.temperature]
source = "met"

[parameters.temperature.metadata]
instrument = "vaisala_hmp155"
serial_number = "V2340123"
installation_height = "2.0 m"
comment = "Sensor calibrated in December 2023"

[parameters.relative_humidity]
source = "met"

[parameters.relative_humidity.metadata]
instrument = "vaisala_hmp155"
serial_number = "V2340123"
installation_height = "2.0 m"

[parameters.wind_speed]
source = "met"

[parameters.wind_speed.metadata]
instrument = "rm_young_05103"
serial_number = "W4567"
installation_height = "10.0 m"

[parameters.wind_direction]
source = "met"

[parameters.wind_direction.metadata]
instrument = "rm_young_05103"
serial_number = "W4567"
installation_height = "10.0 m"

[parameters.pressure]
source = "nldas2"

[parameters.precipitation]
source = "nldas2"

[parameters.global_shortwave]
source = "nldas2"
```

The `metfile` parameter points to your existing station data file in MetForce's text format. This file contains your high-quality observations. By setting `source = "met"` for temperature, humidity, and wind, you tell MetForce to pull these variables from the station file.

The metadata sections for the station variables are where the instrument library shines. By specifying `instrument = "vaisala_hmp155"`, you reference an entry in MetForce's instrument library. The system automatically includes all the instrument's specifications in the NetCDF metadata: the fact that it is a Vaisala HMP155 thermohygrometer, its measurement ranges and accuracies, and its response characteristics.

You supplement the automatic instrument documentation with site-specific details. The serial number identifies the specific sensor, which matters if you later need to track calibration history or investigate data quality issues. The installation height documents where the sensor was mounted, which is essential context for anyone interpreting the measurements.

The custom comment notes that the sensor was recently calibrated. This kind of local knowledge is invaluable for understanding data quality but would be lost without explicit documentation.

For the NLDAS-2 variables (pressure, precipitation, and solar radiation), you do not need metadata sections because the automatic provenance system handles everything. The system recognizes these as NLDAS-2 data and documents them appropriately.

When you open the resulting NetCDF file, you will see that temperature, humidity, and wind have detailed instrument provenance, while pressure, precipitation, and radiation have NLDAS-2 model provenance. The file is honest about its mixed heritage, allowing users to assess the quality and appropriate uses of each variable independently.

### Adding Custom Documentation

Sometimes you need to document aspects of your data that are not captured by instruments or standard sources. Let me show you how to add arbitrary custom documentation.

Suppose you applied a correction to your pressure data based on a comparison with a nearby reference station, or you want to note that precipitation measurements during winter may include snow that was not heated and melted. You can add these notes through custom metadata:

```toml
[parameters.pressure]
source = "nldas2"

[parameters.pressure.metadata]
comment = "Values adjusted by +1.2 mbar to match reference station WK23 located 5 km northeast"
references = "Correction methodology: Smith et al. 2020, doi:10.xxx/xxx"

[parameters.precipitation]
source = "met"

[parameters.precipitation.metadata]
instrument = "texas_electronics_tr525"
comment = "Winter measurements may undercount snow. Gauge not heated. Estimated 10-15% underestimate during snow events."
```

These custom comments appear in the NetCDF file alongside the automatic provenance documentation. The pressure variable will show both the standard NLDAS-2 provenance and your note about the adjustment. The precipitation variable will show the instrument details and your cautionary note about winter measurements.

You can add any attributes you want through the metadata section. If you need to document a funding source, add a `funding` attribute. If you need to note who should be contacted for questions about the data, add a `contact` attribute. The system passes these through to the NetCDF file unchanged.

This flexibility means you can use MetForce's automatic documentation as a foundation and build whatever additional documentation structure your project needs.

### Working with Output Formats

MetForce can produce three output formats, and understanding when to use each is important for your workflow.

The NetCDF format is the primary output and should be your default choice. NetCDF files are self-documenting, efficient to work with, and broadly supported by scientific software. They preserve all the provenance information that MetForce generates. Use NetCDF when you need long-term archival, when you will share data with collaborators, or when you want to use modern analysis tools.

The legacy text format (`.met` files) exists for compatibility with older models and tools that cannot read NetCDF. These files are human-readable plain text with fixed column widths, similar to the format MetForce has historically produced. However, they have significant limitations: they cannot carry detailed metadata, they are inefficient for large datasets, and they are easy to corrupt by editing. Use text format only when required by legacy software.

The `format = "both"` option creates both a NetCDF file and a text file from the same data. This is useful during transitions when you are moving from legacy tools to modern ones but still need to support both. The NetCDF file preserves all provenance, while the text file provides compatibility.

You control the output format in the configuration:

```toml
[output]
format = "netcdf"  # or "met" or "both"
```

For the vast majority of new work, you should use `format = "netcdf"`. The additional capabilities of NetCDF—self-documentation, provenance, efficiency, broad tool support—far outweigh any advantages of text files.

### Converting Between Formats

Sometimes you receive a NetCDF file but need to provide data to a legacy tool that requires text format. MetForce includes a bidirectional converter that handles this situation while preserving as much information as possible.

To convert NetCDF to text format, use the `nc_to_met` script:

```bash
nc_to_met my_data.nc -o output_file.met
```

This reads the NetCDF file, extracts all the data variables, and writes them to a text file in MetForce's standard format. The script automatically handles unit conversions (Pascal to millibar for pressure, fraction to percent for humidity) and includes all required empty columns for compatibility with legacy tools.

Note that this conversion necessarily loses information. The text format cannot carry the detailed provenance, instrument specifications, and quality documentation that exist in the NetCDF file. The text file only preserves the data values and basic location information. This is why NetCDF should be your primary format, with text conversion done only when necessary for compatibility.

Going the other direction, you can convert text files to NetCDF to add provenance documentation to historical data:

```bash
# Edit a configuration file that describes the text file
# Then run MetForce normally, specifying the text file as input
metforce config_with_text_input.toml
```

In this case, MetForce reads the text file as if it were station data and creates a NetCDF file with as much provenance as you specify in the configuration. This is useful for preserving historical datasets with proper documentation.

---

## 5. Developer Guide: Extending MetForce {#developer-guide}

### Adding a New Data Source

Let me walk you through adding support for a new meteorological data source, using a hypothetical example of integrating the ERA5 reanalysis product. This process demonstrates how MetForce's architecture makes it straightforward to add new data providers while maintaining consistent provenance documentation.

The first step is creating a processing function that knows how to fetch and process data from your new source. This function goes in a new file `metforce/processing/era5.py`:

```python
"""ERA5 reanalysis data processing."""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd
import xarray as xr
import cdsapi  # ERA5 API client


def process_era5_data(
    parameters: Dict[str, Any],
    *,
    latitude: float,
    longitude: float,
    date_range: pd.DatetimeIndex,
    **kwargs
) -> pd.DataFrame:
    """
    Fetch and process ERA5 reanalysis data.
    
    Args:
        parameters: Parameter configuration dict
        latitude: Site latitude
        longitude: Site longitude
        date_range: Timestamps to retrieve
        
    Returns:
        DataFrame with requested parameters
    """
    # Identify which ERA5 variables we need
    era5_params = [
        param for param, config in parameters.items()
        if config.get("source") == "era5"
    ]
    
    if not era5_params:
        return pd.DataFrame(index=date_range)
    
    # Map MetForce parameters to ERA5 variable names
    era5_var_map = {
        "temperature": "2m_temperature",
        "pressure": "surface_pressure",
        "relative_humidity": "2m_dewpoint_temperature",  # Convert to RH
        "wind_speed": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        # ... etc
    }
    
    # Fetch data from ERA5
    client = cdsapi.Client()
    era5_vars = []
    for param in era5_params:
        era5_vars.extend(
            [era5_var_map[param]] 
            if isinstance(era5_var_map[param], str) 
            else era5_var_map[param]
        )
    
    # Request data
    result = client.retrieve(
        'reanalysis-era5-single-levels',
        {
            'product_type': 'reanalysis',
            'variable': era5_vars,
            'year': [str(y) for y in date_range.year.unique()],
            'month': [str(m) for m in date_range.month.unique()],
            'day': [str(d) for d in date_range.day.unique()],
            'time': [f"{h:02d}:00" for h in date_range.hour.unique()],
            'area': [latitude + 0.5, longitude - 0.5, 
                    latitude - 0.5, longitude + 0.5],  # Bounding box
            'format': 'netcdf',
        }
    )
    
    # Load and process the downloaded data
    ds = xr.open_dataset(result)
    
    # Interpolate to exact location
    ds = ds.interp(latitude=latitude, longitude=longitude, method='linear')
    
    # Convert to DataFrame with MetForce column names
    df = pd.DataFrame(index=date_range)
    
    if "temperature" in era5_params:
        df["temperature"] = ds["2m_temperature"].values - 273.15  # K to C
    
    if "pressure" in era5_params:
        df["pressure"] = ds["surface_pressure"].values / 100  # Pa to mbar
    
    if "relative_humidity" in era5_params:
        # Convert dewpoint to RH
        temp_k = ds["2m_temperature"].values
        dewpoint_k = ds["2m_dewpoint_temperature"].values
        df["relative_humidity"] = _dewpoint_to_rh(temp_k, dewpoint_k)
    
    # ... handle other parameters
    
    return df


def _dewpoint_to_rh(temp_k: np.ndarray, dewpoint_k: np.ndarray) -> np.ndarray:
    """Convert temperature and dewpoint to relative humidity."""
    # Magnus formula
    a = 17.27
    b = 237.7
    
    temp_c = temp_k - 273.15
    dewpoint_c = dewpoint_k - 273.15
    
    alpha_temp = (a * temp_c) / (b + temp_c)
    alpha_dewpoint = (a * dewpoint_c) / (b + dewpoint_c)
    
    rh = 100 * np.exp(alpha_dewpoint - alpha_temp)
    return np.clip(rh, 0, 100) / 100  # Convert to fraction
```

This processing function handles the mechanics of fetching ERA5 data and converting it to MetForce's internal format. The function signature matches the pattern MetForce expects: it receives parameters describing what to fetch, location information, the time range, and returns a DataFrame with the requested variables.

Next, register your new source with MetForce by creating a data source strategy in `metforce/sources.py`:

```python
class ERA5DataSourceStrategy(DataSourceStrategy):
    """Strategy for ERA5 reanalysis data."""
    
    source_name = "era5"
    processing_function = process_era5_data
```

Then add it to the registry:

```python
DATA_SOURCE_REGISTRY = {
    "station": StationDataSourceStrategy(),
    "nldas2": NLDAS2DataSourceStrategy(),
    "era5": ERA5DataSourceStrategy(),  # Your new source
    # ... other sources
}
```

Now ERA5 is available as a data source. Users can specify `source = "era5"` in their configuration files, and MetForce will automatically route to your processing function.

The final step is adding provenance support so that ERA5 data is automatically documented. Create a provenance function in `metforce/output.py`:

```python
def _add_era5_provenance(
    ds: xr.Dataset,
    cf_var: str,
    param_config: Dict[str, Any],
    merged_metadata: Dict[str, Any]
) -> None:
    """
    Add provenance for ERA5 reanalysis data.
    
    Documents:
    - Data source (ERA5)
    - Model details (IFS)
    - Spatial resolution (0.25 degree)
    - Temporal resolution (hourly)
    - Processing (spatial interpolation)
    - References
    """
    ds[cf_var].attrs["source"] = "era5"
    ds[cf_var].attrs["data_type"] = "reanalysis"
    ds[cf_var].attrs["model"] = "ERA5 (ECMWF Reanalysis v5)"
    ds[cf_var].attrs["spatial_resolution"] = "0.25 degree (~31 km)"
    ds[cf_var].attrs["temporal_resolution"] = "1 hour"
    
    # Auto-generate comment
    auto_comment = (
        "Derived from ERA5 reanalysis data. "
        "ERA5 is ECMWF's fifth generation atmospheric reanalysis. "
        "Spatially interpolated to site location. "
        "Hourly temporal resolution."
    )
    
    # Merge with user comment
    user_comment = merged_metadata.get("comment", "")
    comment_replace = merged_metadata.get("comment_replace")
    
    if comment_replace:
        ds[cf_var].attrs["comment"] = comment_replace
    elif user_comment:
        ds[cf_var].attrs["comment"] = f"{auto_comment} {user_comment}"
    else:
        ds[cf_var].attrs["comment"] = auto_comment
    
    # References
    default_ref = "doi:10.1002/qj.3803"  # ERA5 paper
    if merged_metadata.get("references"):
        ds[cf_var].attrs["references"] = f"{default_ref}, {merged_metadata['references']}"
    else:
        ds[cf_var].attrs["references"] = default_ref
    
    # Quality assessment
    _add_quality_assessment(ds, cf_var)
```

Finally, register this provenance function in the dispatch logic:

```python
# In build_netcdf_dataset(), update the provenance dispatch:
if source == "era5":
    _add_era5_provenance(ds, cf_var, param_config, merged_metadata)
```

Now when users specify ERA5 data, MetForce automatically documents that it came from ERA5, notes the model characteristics, provides scientific references, and describes the processing applied. The provenance happens automatically without users having to know anything about ERA5's specifics.

This same pattern works for any data source: create a processing function, register it as a strategy, and add a provenance function. The modular design makes it straightforward to extend MetForce with new capabilities.

### Adding a New Derived Variable

Sometimes you want to compute a variable from other variables, like calculating wind speed from u and v components, or deriving potential temperature from temperature and pressure. Let me show you how to add support for derived variables.

Suppose you want to add support for potential temperature, which is calculated from temperature and pressure using thermodynamic relationships. First, create a derivation function:

```python
# In metforce/processing/derived.py

def derive_potential_temperature(
    df: pd.DataFrame,
    reference_pressure: float = 100000.0  # Pa
) -> pd.Series:
    """
    Compute potential temperature from temperature and pressure.
    
    Potential temperature is the temperature a parcel would have if 
    brought adiabatically to a reference pressure (typically 1000 mbar).
    
    Args:
        df: DataFrame with 'temperature' (C) and 'pressure' (mbar) columns
        reference_pressure: Reference pressure in Pa
        
    Returns:
        Series of potential temperatures in Celsius
    """
    import numpy as np
    
    # Constants
    R_d = 287.05  # Gas constant for dry air (J/(kg·K))
    c_p = 1005.0  # Specific heat at constant pressure (J/(kg·K))
    kappa = R_d / c_p  # Poisson constant
    
    # Convert inputs to SI
    temp_k = df["temperature"] + 273.15  # C to K
    pressure_pa = df["pressure"] * 100   # mbar to Pa
    
    # Compute potential temperature
    theta_k = temp_k * (reference_pressure / pressure_pa) ** kappa
    
    # Convert back to Celsius
    theta_c = theta_k - 273.15
    
    return theta_c
```

Register this as a derived source:

```python
# In metforce/sources.py

def process_derived_data(
    parameters: Dict[str, Any],
    *,
    dataframes: Dict[str, pd.DataFrame],
    **kwargs
) -> pd.DataFrame:
    """Process derived variables computed from other variables."""
    
    # Merge all available data
    combined = pd.concat([df for df in dataframes.values()], axis=1)
    
    result = pd.DataFrame(index=combined.index)
    
    for param, config in parameters.items():
        source = config.get("source", "")
        
        if source == "potential_temperature":
            if "temperature" not in combined or "pressure" not in combined:
                raise ValueError(
                    "Potential temperature requires both temperature and pressure"
                )
            result[param] = derive_potential_temperature(combined)
    
    return result
```

Add provenance documentation:

```python
# In metforce/output.py

def _add_potential_temperature_provenance(
    ds: xr.Dataset,
    cf_var: str,
    param_config: Dict[str, Any],
    merged_metadata: Dict[str, Any]
) -> None:
    """Add provenance for derived potential temperature."""
    
    ds[cf_var].attrs["source"] = "derived"
    ds[cf_var].attrs["data_type"] = "derived"
    ds[cf_var].attrs["method"] = "Poisson equation from temperature and pressure"
    
    # Reference pressure
    ref_p = param_config.get("reference_pressure", 100000.0)
    ds[cf_var].attrs["reference_pressure"] = f"{ref_p} Pa"
    
    auto_comment = (
        f"Potential temperature computed from air temperature and pressure "
        f"using the Poisson equation with reference pressure {ref_p/100:.0f} mbar. "
        f"Represents the temperature an air parcel would have if brought "
        f"adiabatically to the reference pressure."
    )
    
    # Merge comments as usual
    user_comment = merged_metadata.get("comment", "")
    if merged_metadata.get("comment_replace"):
        ds[cf_var].attrs["comment"] = merged_metadata["comment_replace"]
    elif user_comment:
        ds[cf_var].attrs["comment"] = f"{auto_comment} {user_comment}"
    else:
        ds[cf_var].attrs["comment"] = auto_comment
    
    _add_quality_assessment(ds, cf_var)
```

Now users can request potential temperature in their configuration:

```toml
[parameters.potential_temperature]
source = "potential_temperature"
reference_pressure = 100000  # Optional, defaults to 1000 mbar

[parameters.potential_temperature.metadata]
comment = "Used for stability analysis"
```

The system automatically computes potential temperature from the available temperature and pressure data and documents the calculation method, reference pressure used, and physical meaning.

### Extending the Instrument Library

Adding instruments to the library is straightforward, whether you are adding to the default library or creating your own custom library. Let me show you both approaches.

To add an instrument to your own custom library, create a TOML file with the instrument specifications:

```toml
# my_instruments.toml

[pyranometers.kipp_zonen_cmp22]
manufacturer = "Kipp & Zonen"
model = "CMP22"
category = "pyranometer"
description = "Secondary standard pyranometer for high-accuracy solar radiation measurements"

[pyranometers.kipp_zonen_cmp22.specifications]
spectral_range = "285 to 3000 nm"
response_time = "< 1.7 s (95%)"
sensitivity = "5 to 20 µV/(W/m²)"
temperature_dependence = "< 1% (-10°C to +40°C)"
directional_response = "< 10 W/m² (0° to 80° zenith)"
internal_heating = true

[pyranometers.kipp_zonen_cmp22.installation]
mounting = "Level installation required. Use spirit level or electronic inclinometer."
clearance = "Unobstructed 180° view of sky hemisphere. No shading from structures."
maintenance = "Clean glass dome weekly. Check desiccant monthly."

[thermohygrometers.custom_sensor_a1]
manufacturer = "Custom Instruments Inc."
model = "TH-A1"
category = "thermohygrometer"
description = "Laboratory-calibrated temperature and humidity sensor"

[thermohygrometers.custom_sensor_a1.specifications]
temperature_range = "-40 to 60°C"
temperature_accuracy = "±0.1°C"
humidity_range = "0 to 100%"
humidity_accuracy = "±1% (0-90%), ±2% (90-100%)"
response_time_temperature = "20 s in moving air (0.5 m/s)"
response_time_humidity = "15 s (0-90%)"

[thermohygrometers.custom_sensor_a1.calibration]
date = "2024-01-15"
laboratory = "NIST-traceable calibration by AccuStandard Labs"
certificate = "ASL-2024-01234"
```

Reference your custom library in the configuration:

```toml
[output]
instrument_library = "~/metforce/my_instruments.toml"

[parameters.global_shortwave]
source = "met"

[parameters.global_shortwave.metadata]
instrument = "kipp_zonen_cmp22"
serial_number = "240123"
installation_height = "2.0 m"

[parameters.temperature]
source = "met"

[parameters.temperature.metadata]
instrument = "custom_sensor_a1"
serial_number = "THA1-05"
```

The system loads both the default library and your custom library, merging them so you have access to standard instruments plus your additions. When you reference "kipp_zonen_cmp22" or "custom_sensor_a1", the system finds them in your custom library and includes all their specifications in the NetCDF metadata.

If you are developing an instrument specification that should be in the default library (because it is a widely used standard sensor), you would add it to `metforce/data/instruments.toml` following the same format. Then submit a pull request to have it included in the next MetForce release.

### Adding Custom CF Standard Names

Occasionally you need to work with a variable that does not have a CF standard name. This is rare because the CF standard name table is comprehensive, but it happens with specialized measurements or experimental quantities.

When you cannot find an appropriate standard name, you have two options. First, you can petition the CF convention committee to add your variable to the standard name table. This is the right approach for quantities that other researchers are likely to measure and ensures your data will be maximally interoperable. The CF conventions website has a process for proposing new standard names.

Second, for truly specialized variables that are unlikely to be widely used, you can omit the standard_name attribute and rely on the long_name and description to document what the variable represents. MetForce supports this:

```python
# In output.py, when creating a variable without a CF standard name:

_var("my_specialized_measurement", values,
     {
         # No standard_name
         "long_name": "Spectral reflectance at 550 nm wavelength",
         "units": "1",
         "comment": "Measured using custom hyperspectral radiometer",
         "instrument_manufacturer": "Custom Instruments",
         "instrument_model": "HSR-550"
     })
```

The resulting NetCDF file will have a variable without a standard_name attribute. Most software will handle this gracefully, using the long_name for display and the units for computation. The lack of a standard name makes automated processing slightly harder but does not prevent the file from being useful.

Document your non-standard variables carefully in the long_name and comment attributes so that future users understand what they represent. Include references to any papers or documentation that define the measurement.

---

## 6. Visualization and Analysis {#visualization}

### Quick Visual Inspection

The fastest way to understand what is in a NetCDF file is to visualize it. MetForce includes visualization tools designed specifically for meteorological time series. Let me show you how to use them.

Start with the simplest case: plotting a single variable. The plot_variable function creates an interactive time series with a scrubber that lets you zoom into specific time periods:

```python
from metforce.viz import plot_variable

chart = plot_variable(
    "my_site_2024.nc",
    "air_temperature",
    title="Site Temperature 2024"
)

chart.save("temperature.html")
```

This creates an HTML file with an interactive chart. Open it in your web browser and you will see two panels: a main chart showing temperature over time, and a smaller timeline scrubber below it. Click and drag on the scrubber to select a time range, and the main chart zooms to show just that period. This makes it easy to explore patterns at different time scales—you can look at annual trends, then zoom to a particular month, then to a single week, all with simple mouse interactions.

The chart automatically extracts metadata from the NetCDF file. The y-axis label shows "air temperature (°C)" using the long_name and units from the file. Hovering over the line shows a tooltip with the exact timestamp and value. The chart is fully vectorized, so zooming preserves clarity.

For comparing multiple variables, use plot_multiple:

```python
from metforce.viz import plot_multiple

chart = plot_multiple(
    "my_site_2024.nc",
    ["air_temperature", "relative_humidity", "wind_speed"],
    title="Multi-Variable Analysis"
)

chart.save("multi_var.html")
```

This creates a vertically stacked display with each variable in its own panel but sharing a common time axis. The scrubber at the bottom controls all panels simultaneously, so when you zoom to examine a particular week, all variables zoom together. This makes it easy to see correlations—you can watch how temperature and humidity covary, or how wind speed relates to precipitation events.

### Solar Radiation Analysis

Solar radiation data has special visualization needs because it includes multiple components (global, direct, diffuse) that should be compared on the same chart. MetForce includes a specialized radiation plotting function:

```python
from metforce.viz import plot_radiation_components

chart = plot_radiation_components(
    "my_site_2024.nc",
    start_time="2024-06-01",
    end_time="2024-06-30"
)

chart.save("radiation_june.html")
```

This creates a chart showing global, direct, and diffuse radiation as different colored lines on the same axes. The color legend makes it easy to distinguish the components. You can see how global radiation represents the sum of direct and diffuse, watch how the direct fraction changes with weather conditions, and identify clear versus cloudy periods.

The pre-filtering with start_time and end_time reduces the dataset before visualization, which is useful for large files. Visualizing a full year of hourly data can be sluggish in the browser, so filtering to a representative month gives you a responsive visualization while still showing the patterns you need to see.

For assessing atmospheric conditions, the clearness index provides a normalized measure of atmospheric transparency:

```python
from metforce.viz import plot_clearness_index

chart = plot_clearness_index(
    "my_site_2024.nc",
    start_time="2024-06-01",
    end_time="2024-06-30"
)

chart.save("clearness.html")
```

The clearness index is the ratio of observed global radiation to extraterrestrial radiation (what would reach the surface with no atmosphere). Values near one indicate clear skies, while lower values indicate clouds or aerosols. This derived quantity helps you understand atmospheric conditions and validate solar radiation measurements.

### Time Range Selection

All the visualization functions support time range filtering to let you focus on specific periods. You can pre-filter when creating the visualization or use the interactive scrubber to explore dynamically.

Pre-filtering is useful when you want to create a figure for a paper or report showing a specific event or time period:

```python
chart = plot_variable(
    "my_site_2024.nc",
    "wind_speed",
    start_time="2024-09-15",
    end_time="2024-09-17",
    title="Hurricane Event"
)

chart.save("hurricane_winds.html")
```

This creates a chart showing only those three days, making the patterns clear without the clutter of the full year. The time filter happens during data loading, so even for huge files, the visualization remains responsive.

The interactive scrubber complements pre-filtering by letting you explore within the filtered range. If you filter to a month and then use the scrubber to zoom to a particular week, you can examine fine details while still having the broader context visible in the scrubber.

### Statistical Summaries

Beyond visualization, you often need quantitative summaries of your data. The analysis module provides functions for extracting statistics and metadata:

```python
from metforce.analysis import summarize_dataset

summary = summarize_dataset("my_site_2024.nc")
print(summary)
```

This produces a table showing, for each variable: minimum, maximum, mean, standard deviation, number of missing values, units, and data source. This summary gives you a quick health check of your data—are values in reasonable ranges? Are there unexpected missing data gaps? Do statistics match what you expect for your location and time period?

For understanding data provenance, extract the full metadata for a specific variable:

```python
from metforce.analysis import get_provenance

prov = get_provenance("my_site_2024.nc", "air_temperature")
for key, value in prov.items():
    print(f"{key}: {value}")
```

This shows all the provenance attributes: data source, instrument details, processing methods, references, and quality notes. It is like reading the variable's biography—you learn its complete history.

### Integration with Scientific Python

MetForce NetCDF files work seamlessly with the scientific Python ecosystem. You can load them with xarray for analysis, use pandas for tabular operations, or integrate with specialized libraries.

For example, to compute degree days for agricultural applications:

```python
import xarray as xr
import numpy as np

ds = xr.open_dataset("my_site_2024.nc")
temp = ds["air_temperature"]

# Growing degree days (base 10°C)
gdd = (temp - 10).clip(min=0)
cumulative_gdd = gdd.cumsum(dim="time")

print(f"Total growing degree days: {cumulative_gdd[-1].values:.0f}")
```

For wind rose analysis:

```python
from windrose import WindroseAxes
import matplotlib.pyplot as plt

ds = xr.open_dataset("my_site_2024.nc")
speed = ds["wind_speed"].values
direction = ds["wind_from_direction"].values

ax = WindroseAxes.from_ax()
ax.bar(direction, speed, normed=True, opening=0.8, edgecolor='white')
ax.set_legend()
plt.savefig("windrose.png")
```

The CF-compliant structure means you do not need to write custom parsing code or remember what column names mean. The standard names and units make the data self-explanatory, and the rich metadata helps you interpret results correctly.

---

## 7. Best Practices and Troubleshooting {#best-practices}

### Organizing Your Work

Effective data management starts with good organization. I recommend establishing a consistent structure for your MetForce projects that separates raw data, processing configurations, and final outputs.

Create a project directory for each site or analysis:

```
my_project/
  data/
    raw/           # Original station files, never modified
    processed/     # MetForce NetCDF outputs
  config/          # Configuration files
  analysis/        # Analysis scripts and results
  docs/            # Documentation, metadata notes
```

Keep your configuration files under version control (git). They are small text files that document your processing workflow. Being able to see how your configuration evolved over time, or comparing configurations between different sites, provides valuable context.

Store NetCDF files with descriptive names that include the site and time period: `vidalia_2024.nc` is better than `output.nc`. When you have multiple processing runs, include version numbers or dates: `vidalia_2024_v2.nc` or `vidalia_2024_20241104.nc`. This prevents confusion about which file contains what.

Document any manual corrections or special processing in a notes file alongside your configuration. If you manually edited the station data to remove an erroneous spike, note it. If you know certain periods have questionable quality, document why. These notes supplement the automatic provenance in the NetCDF file.

### Data Quality Checks

Always validate your output before using it in analysis or modeling. MetForce tries to catch problems automatically, but you should verify that results make sense for your location and time period.

Start with basic range checks. Open your NetCDF file and check the summary statistics:

```python
from metforce.analysis import summarize_dataset

summary = summarize_dataset("my_output.nc")
print(summary)
```

Look for values outside expected ranges. Temperature of 150°C suggests a unit error (likely Kelvin instead of Celsius). Humidity of 15 instead of 0.15 suggests a percentage instead of fraction. Wind speeds of 500 m/s indicate corrupt data.

Check for missing data patterns. A few isolated missing values are normal, but long gaps or systematic patterns (like missing every night) suggest problems with the data source or processing.

Visualize every variable at least briefly. Plot the full time series and scan for obvious issues: flat lines indicating sensor failures, spikes indicating erroneous readings, or unexpected periodicities. Even a quick visual scan catches problems that might not show up in statistics.

For mixed-source datasets, verify that different sources agree in overlapping variables. If you have both station and NLDAS-2 data, compare their pressures or temperatures in a test file. Large discrepancies suggest problems with units, location coordinates, or time zones.

### Common Issues and Solutions

**Problem: Time zones are wrong**

Meteorological data comes in different time zones: UTC, local standard time, local solar time. MetForce assumes UTC for consistency, but if your source data uses a different time zone, you need to convert it.

For station data in local time, document the time zone in your source files and convert to UTC before creating the MetForce input file. For model data, check the documentation—most reanalysis products use UTC, but some regional models use local time.

**Problem: Spatial interpolation looks wrong**

When extracting gridded data like NLDAS-2, MetForce interpolates from the model grid to your exact location. If your site is in complex terrain (mountains, coastline), the interpolation might not capture local conditions well.

Check the elevation of the nearest grid points versus your actual site elevation. Large elevation differences (more than 200-300 meters) mean the interpolated data might not represent your site well. Consider using a higher-resolution product if available, or using station data for the most critical variables.

**Problem: Solar radiation is all zeros at night**

This is correct behavior. Solar radiation is zero when the sun is below the horizon. If you see zeros during daytime, check your latitude and longitude—reversed coordinates or wrong sign can place you in the wrong hemisphere. Check the time zone—if your timestamps are off by 12 hours, day and night are swapped.

**Problem: NetCDF file is huge**

NetCDF files can be compressed, which typically reduces size by 50-80% for meteorological data. MetForce uses reasonable compression by default, but you can adjust it if needed.

Very large files usually indicate you have too much data for your needs. Do you really need hourly data for 50 years? Consider aggregating to daily resolution or splitting into annual files. For variables you rarely use, consider storing them in a separate file.

**Problem: Legacy software cannot read my NetCDF file**

Some old models require specific variable names, dimension orders, or attribute conventions. Use the `nc_to_met` converter to create text files for stubborn tools. Better yet, check if the legacy software has been updated to support NetCDF—many older models have added NetCDF support in recent versions.

If you must modify the NetCDF file for compatibility, keep the original MetForce output and create a modified copy for the legacy tool. Document what modifications you made and why. Never edit the original output because you will lose provenance information.

### Performance Optimization

For large processing jobs (years of data at high resolution, multiple sites), a few optimizations can make MetForce much faster.

Enable VegaFusion for visualization of large datasets:

```python
import altair as alt
alt.data_transformers.enable('vegafusion')
```

This delegates data transformations to a fast Rust-based engine, making visualizations of large datasets much more responsive.

For NLDAS-2 downloads, MetForce fetches data in parallel. The default is 8 concurrent downloads, but on fast networks you can increase this. Be respectful of NASA's servers—don't set this too high.

If you process many sites with the same time range, download NLDAS-2 data once to a local directory and reuse it rather than downloading separately for each site. MetForce can read from local files instead of making repeated downloads.

For very long time series (decades), consider processing in chunks and combining the results. Process each year separately, then use xarray to concatenate the NetCDF files. This uses less memory and makes it easier to recover from errors without starting over.

### Getting Help

When you encounter a problem you cannot solve, gather information before asking for help. Provide:

- Your configuration file
- The error message (complete, not just the last line)
- The MetForce version you are using
- A description of what you expected versus what happened

If the problem involves data quality, include a small sample of your data and a visualization showing the issue. "My temperatures look wrong" is hard to debug, but "My temperatures are systematically 10°C too high compared to nearby stations" provides actionable information.

Check the MetForce documentation and issue tracker on GitHub. Many common problems have been encountered and solved before. Search for error messages or keywords related to your problem.

When reporting bugs, try to create a minimal example that reproduces the problem. If your full configuration fails, gradually simplify it until you find the smallest configuration that shows the issue. This helps developers diagnose the problem quickly and often helps you understand the root cause yourself.

---

This documentation should give you a comprehensive understanding of MetForce's NetCDF output and provenance tracking system. The key principles to remember are: provenance should be automatic, metadata should travel with data forever, and CF conventions ensure long-term usability. Start simple with automatic documentation, then progressively enhance with custom metadata as your needs grow. The system is designed to make it easy to do the right thing, so your data remains valuable and understandable for years to come.